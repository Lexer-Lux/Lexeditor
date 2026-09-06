"""Archive and remove unchanged issue comments; never PR reviews or issue #86.

Run archive, commit/push the worklog source records, then cleanup.
No game codex import or semantic worklog merge occurs.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

REPO = 'Lexer-Lux/Lexeditor'
PLAN = Path('worklog/migrations/comment-cleanup-plan.json')
RESULT = Path('comment-cleanup-result.json')
EXCLUDED = {86}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def api(path: str, payload: dict | None = None):
    args = ['gh', 'api', path]
    if payload is not None:
        args += ['--method', 'POST', '--input', '-']
    p = subprocess.run(args, input=None if payload is None else json.dumps(payload),
                       text=True, capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError(p.stderr[-1200:])
    result = json.loads(p.stdout)
    if isinstance(result, dict) and result.get('errors'):
        raise RuntimeError(json.dumps(result['errors']))
    return result


def pages(path: str) -> list:
    p = subprocess.run(['gh', 'api', '--paginate', '--slurp', path], text=True,
                       capture_output=True, timeout=180)
    if p.returncode:
        raise RuntimeError(p.stderr[-1200:])
    return [row for page in json.loads(p.stdout) for row in page]


def save(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def archive() -> None:
    spec = importlib.util.spec_from_file_location('knowledge_store', Path('tools/knowledge_store.py'))
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    issues = {i['number']: i for i in pages(f'repos/{REPO}/issues?state=all&per_page=100')
              if 'pull_request' not in i and i['number'] not in EXCLUDED}
    comments = [c for c in pages(f'repos/{REPO}/issues/comments?per_page=100')
                if int(c['issue_url'].rsplit('/', 1)[1]) in issues]
    registry_path = Path('worklog/attachments/index.json')
    registry = json.loads(registry_path.read_text('utf-8')) if registry_path.exists() else {}
    records = []
    for c in comments:
        n = int(c['issue_url'].rsplit('/', 1)[1])
        path = store.store(n, 'comment', c)
        failed = store.attachments(c.get('body') or '', registry)
        attachments = [registry[u] for u in set(store.URL.findall(c.get('body') or ''))
                       if u in registry and 'path' in registry[u]]
        records.append({'id': c['id'], 'node_id': c['node_id'], 'issue': n,
                        'updated_at': c['updated_at'], 'body_sha256': digest(c.get('body') or ''),
                        'archive': path.as_posix(), 'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'attachments': attachments, 'missing_attachments': failed})
    save(registry_path, registry)
    save(PLAN, {'repository': REPO, 'excluded': sorted(EXCLUDED), 'records': records})
    print(json.dumps({'archived': len(records), 'blocked_attachments': sum(bool(c['missing_attachments']) for c in records)}))


def committed(path: str) -> bytes:
    return subprocess.check_output(['git', 'show', f'HEAD:{path}'])


def current_nodes(rows: list[dict]) -> dict:
    result = api('graphql', {'query': 'query($ids:[ID!]!){nodes(ids:$ids){... on IssueComment{id body updatedAt}}}',
                             'variables': {'ids': [c['node_id'] for c in rows]}})
    return {n['id']: n for n in result['data']['nodes'] if n}


def same(c: dict, node: dict | None) -> bool:
    return bool(node and node['updatedAt'] == c['updated_at'] and digest(node['body']) == c['body_sha256'])


def cleanup() -> None:
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'worklog'], check=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/master'], check=True)
    plan = json.loads(committed(PLAN.as_posix()))
    assert plan['repository'] == REPO and plan['excluded'] == sorted(EXCLUDED)
    report = {'deleted': [], 'already_absent': [], 'changed': [], 'attachment_blocked': [],
              'excluded': sorted(EXCLUDED), 'errors': []}
    eligible = []
    for c in plan['records']:
        assert c['issue'] not in EXCLUDED
        raw = committed(c['archive'])
        assert hashlib.sha256(raw).hexdigest() == c['archive_sha256']
        r = json.loads(raw)['record']
        assert r['id'] == c['id'] and digest(r.get('body') or '') == c['body_sha256']
        if c['missing_attachments']:
            report['attachment_blocked'].append(c['id'])
            continue
        for a in c['attachments']:
            assert hashlib.sha256(committed(a['path'])).hexdigest() == a['sha256']
        eligible.append(c)
    try:
        # Each small sequential batch is read immediately before mutation.
        # On any ambiguous write failure STOP, never replay the mutation.
        for start in range(0, len(eligible), 5):
            batch = eligible[start:start + 5]
            fresh = current_nodes(batch)
            safe = []
            for c in batch:
                node = fresh.get(c['node_id'])
                if node is None:
                    report['already_absent'].append(c['id'])
                elif same(c, node):
                    safe.append(c)
                else:
                    report['changed'].append(c['id'])
            if safe:
                variables = {f'id{k}': c['node_id'] for k, c in enumerate(safe)}
                declaration = ','.join(f'${k}:ID!' for k in variables)
                fields = ' '.join(f'd{k}:deleteIssueComment(input:{{id:$id{k}}}){{clientMutationId}}'
                                  for k in range(len(safe)))
                api('graphql', {'query': f'mutation({declaration}){{{fields}}}', 'variables': variables})
                report['deleted'].extend(c['id'] for c in safe)
            save(RESULT, report)
            if start % 100 == 0:
                print(f"Verified removals: {len(report['deleted'])}", flush=True)
            time.sleep(1.5)
    except Exception as error:
        report['errors'].append(str(error))
        raise
    finally:
        save(RESULT, report)
    issue_numbers = {r['issue'] for r in plan['records']}
    remaining = [c for c in pages(f'repos/{REPO}/issues/comments?per_page=100')
                 if int(c['issue_url'].rsplit('/', 1)[1]) in issue_numbers]
    report['remaining'] = [{'id': c['id'], 'issue': int(c['issue_url'].rsplit('/',1)[1])} for c in remaining]
    save(RESULT, report)
    print(json.dumps({k: len(v) if isinstance(v,list) else v for k,v in report.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['archive', 'cleanup'])
    args = parser.parse_args()
    archive() if args.mode == 'archive' else cleanup()
