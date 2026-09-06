"""Lossless source storage. No semantic summarization and no implicit deletion.

Run archive before commit/push; cleanup refuses to use uncommitted records.
The GitHub CLI supplies authentication. Never pass issue text to a shell.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.parse
import urllib.request

REPO = 'Lexer-Lux/Lexeditor'
ROOT = Path('worklog/issues')
CONTROL = Path('worklog/migrations/comment-archive')
ATTACHMENTS = Path('worklog/attachments')
URL = re.compile(r'https://(?:github\.com/user-attachments/(?:assets|files)/|user-images\.githubusercontent\.com/)[^\s<>\)\]"\']+')
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{32,}|github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def write(path: Path, data: bytes, immutable: bool = False) -> None:
    if path.is_symlink():
        raise RuntimeError(f'Refusing symlink: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists() and path.read_bytes() != data:
        raise RuntimeError(f'Immutable source collision: {path}')
    path.write_bytes(data)
    if path.read_bytes() != data:
        raise RuntimeError(f'Readback mismatch: {path}')


def gh(endpoint: str, payload: dict | None = None) -> object:
    args = ['gh', 'api', endpoint]
    data = None
    if payload is not None:
        args += ['--method', 'POST', '--input', '-']
        data = json.dumps(payload)
    p = subprocess.run(args, input=data, capture_output=True, text=True, timeout=90)
    if p.returncode:
        # Stop on rate/access failures; do not loop or switch identities.
        raise RuntimeError(f'GitHub request failed: {endpoint}: {p.stderr[-1000:]}')
    return json.loads(p.stdout) if p.stdout.strip() else None


def all_pages(endpoint: str) -> list:
    p = subprocess.run(['gh', 'api', '--paginate', '--slurp', endpoint], capture_output=True,
                       text=True, timeout=180)
    if p.returncode:
        raise RuntimeError(p.stderr[-1000:])
    return [item for page in json.loads(p.stdout) for item in page]


def store(number: int, kind: str, record: dict) -> Path:
    body = record.get('body') or ''
    if SECRET.search(body):
        raise RuntimeError(f'Possible credential in #{number}; no publication or deletion allowed')
    wrapper = {'schema': 1, 'repository': REPO, 'issue': number, 'kind': kind,
               'body_sha256': digest(body.encode('utf-8')), 'record': record}
    data = encoded(wrapper)
    path = ROOT / f'github-{number}' / 'sources' / f'{kind}-{record.get("id", number)}-{digest(data)}.json'
    write(path, data, immutable=True)
    return path


class AttachmentRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        host = urllib.parse.urlparse(url).hostname or ''
        parsed = urllib.parse.urlparse(url)
        github_asset = re.fullmatch(r'github-production-(?:user-asset-[a-z0-9-]+|repository-file-[a-z0-9]+|release-asset-[a-z0-9]+)\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com', host)
        if parsed.scheme != 'https' or not (host == 'github.com' or host.endswith('.githubusercontent.com') or github_asset):
            raise RuntimeError(f'Unexpected attachment redirect host: {host}')
        return super().redirect_request(req, fp, code, msg, headers, url)


def attachments(body: str, known: dict) -> list[str]:
    failed = []
    opener = urllib.request.build_opener(AttachmentRedirect())
    for url in sorted(set(URL.findall(body))):
        old = known.get(url)
        if old and old.get('path') and Path(old['path']).exists():
            if digest(Path(old['path']).read_bytes()) == old['sha256']:
                continue
        try:
            ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if ext in {'.exe', '.dll', '.asi', '.ttf', '.otf', '.woff', '.woff2'}:
                raise RuntimeError('Binary/font publication requires separate handling')
            with opener.open(url, timeout=20) as response:
                content_type = response.headers.get_content_type()
                data = response.read(20_000_001)
            if len(data) > 20_000_000 or content_type == 'text/html':
                raise RuntimeError('Oversized attachment or an HTML access/error page')
            ext = { 'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif',
                    'image/webp': '.webp', 'video/mp4': '.mp4' }.get(content_type, ext or '.bin')
            path = ATTACHMENTS / (digest(data) + ext)
            write(path, data, immutable=True)
            known[url] = {'path': path.as_posix(), 'sha256': digest(data), 'bytes': len(data)}
        except Exception as error:
            known[url] = {'error': str(error)}
            failed.append(url)
    return failed


def regenerate(number: int, current: dict | None = None) -> None:
    directory = ROOT / f'github-{number}'
    sources = []
    for path in sorted((directory / 'sources').glob('*.json')):
        obj = json.loads(path.read_text('utf-8'))
        sources.append((path, obj))
    sources.sort(key=lambda pair: (pair[1]['record'].get('created_at') or '',
                                  pair[1]['record'].get('updated_at') or '', pair[0].name))
    text = '# Complete archived source text\n\nHistorical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.\n'
    for path, obj in sources:
        r = obj['record']; author = (r.get('user') or {}).get('login', 'not recorded')
        text += f'\n## {obj["kind"]} {r.get("id", number)} — {author}\n\n'
        text += f'Source: {r.get("html_url") or r.get("url") or "not recorded"}\n\n'
        text += f'Created: {r.get("created_at")}; updated: {r.get("updated_at")}\n\n'
        text += f'Exact metadata: [source record](sources/{path.name}).\n\n'
        text += (r.get('body') or '(No body was present in this captured version.)') + '\n'
    write(directory / 'conversation.md', text.encode('utf-8'))
    handoff = ROOT / f'github-{number}.md'
    pointer = f'[Full request and discussion archive](github-{number}/conversation.md)'
    if not handoff.exists():
        title = (current or {}).get('title', f'Issue {number}')
        text = f'# #{number}: {title}\n\n{pointer}\n\n## Requirements and decisions\n\nRecover the complete scope from the linked verbatim sources before implementation or status changes. The short GitHub summary is not the full specification. Do not infer that missing chat text was never supplied.\n\n## Current implementation and evidence\n\nReconcile live code, PRs and existing topic/session worklogs. This archive import makes no build, deployment or gameplay-success claim.\n\n## Next agent work\n\nRead the source records and preserve the latest explicit human corrections. Update this handoff, not a shared global Worklog.txt.\n'
        write(handoff, text.encode('utf-8'))
    elif pointer not in handoff.read_text('utf-8'):
        write(handoff, handoff.read_bytes() + ('\n\n## Preserved source records\n\n' + pointer + '\n').encode())


def archive(baseline: Path | None, excluded: set[int] | None = None) -> dict:
    issues = all_pages(f'repos/{REPO}/issues?state=all&per_page=100&sort=created&direction=asc')
    current = {i['number']: i for i in issues if 'pull_request' not in i and i['number'] not in (excluded or set())}
    comments = all_pages(f'repos/{REPO}/issues/comments?per_page=100&sort=created&direction=asc')
    comments = [c for c in comments if int(c['issue_url'].rsplit('/', 1)[1]) in current]
    old_issues, old_comments = [], []
    if baseline:
        for name, target in [('issues-before.json', old_issues), ('comments-before.json', old_comments)]:
            path = baseline / name
            if path.exists(): target.extend(json.loads(path.read_text('utf-8')))
    for i in old_issues:
        if 'pull_request' not in i and i['number'] in current: store(i['number'], 'issue', i)
    for c in old_comments:
        number = int(c['issue_url'].rsplit('/', 1)[1])
        if number in current: store(number, 'comment', c)
    for i in current.values(): store(i['number'], 'issue', i)
    registry_path = ATTACHMENTS / 'index.json'
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    pending = []
    for c in comments:
        number = int(c['issue_url'].rsplit('/', 1)[1])
        path = store(number, 'comment', c)
        missing = attachments(c.get('body') or '', registry)
        pending.append({'id': c['id'], 'node_id': c['node_id'], 'issue': number,
                        'body_sha256': digest((c.get('body') or '').encode()),
                        'updated_at': c['updated_at'], 'archive': path.as_posix(),
                        'archive_sha256': digest(path.read_bytes()), 'missing_attachments': missing})
    for i in current.values():
        attachments(i.get('body') or '', registry)
        regenerate(i['number'], i)
    # Also retain attachment references in older versions. Failures never authorize deletion.
    for r in old_issues + old_comments: attachments(r.get('body') or '', registry)
    write(registry_path, encoded(registry))
    snapshot = {'repository': REPO, 'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'issues': len(current), 'comments': len(comments), 'pending': pending,
                'attachment_failures': {k:v for k,v in registry.items() if 'error' in v}}
    write(CONTROL / 'snapshot.json', encoded(snapshot))
    return {'issues':len(current), 'comments_archived':len(comments),
            'comments_blocked_by_attachments':sum(bool(p['missing_attachments']) for p in pending),
            'attachment_failures':len(snapshot['attachment_failures'])}


def cleanup() -> dict:
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'worklog'], check=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/master'], check=True)
    snapshot = json.loads((CONTROL / 'snapshot.json').read_text())
    if snapshot['repository'] != REPO: raise RuntimeError('Wrong archive repository')
    registry = json.loads(subprocess.check_output(['git', 'show', f'HEAD:{ATTACHMENTS / "index.json"}']))
    candidates = snapshot['pending']; deleted=[]; skipped=[]
    verified_attachments = set()
    try:
        for start in range(0, len(candidates), 10):
            batch = candidates[start:start+10]
            for c in batch:
                data = subprocess.check_output(['git','show',f'HEAD:{c["archive"]}'])
                if digest(data) != c['archive_sha256']: raise RuntimeError('Committed archive mismatch')
                record = json.loads(data)
                if record.get('repository') != REPO or record.get('issue') != c['issue'] or record['record']['id'] != c['id']:
                    raise RuntimeError('Archive identity mismatch')
                for url in set(URL.findall(record['record'].get('body') or '')):
                    if url in verified_attachments or url in c['missing_attachments']: continue
                    asset = registry.get(url, {})
                    if not asset.get('path') or asset.get('error'): raise RuntimeError('Missing committed attachment')
                    path = Path(asset['path'])
                    if path.is_absolute() or '..' in path.parts or path.parts[:2] != ('worklog', 'attachments'):
                        raise RuntimeError('Unsafe archived attachment path')
                    saved = subprocess.check_output(['git', 'show', f'HEAD:{path.as_posix()}'])
                    if digest(saved) != asset['sha256']: raise RuntimeError('Committed attachment mismatch')
                    verified_attachments.add(url)
            query = 'query($ids:[ID!]!){nodes(ids:$ids){... on IssueComment{id body updatedAt}}}'
            fresh = gh('graphql', {'query':query,'variables':{'ids':[c['node_id'] for c in batch]}})
            if fresh.get('errors'): raise RuntimeError('Could not re-read comments; deletion stopped')
            nodes = {n['id']: n for n in fresh['data']['nodes'] if n}
            safe=[]
            for c in batch:
                n = nodes.get(c['node_id'])
                if c['missing_attachments'] or not n or n['updatedAt'] != c['updated_at'] or digest(n['body'].encode()) != c['body_sha256']:
                    skipped.append(c['id']); continue
                safe.append(c)
            if not safe: continue
            # An API timeout does not prove the mutation failed. Before a
            # bounded retry, identify which exact comments still exist.
            for attempt in range(3):
                variables = {f'id{k}':c['node_id'] for k,c in enumerate(safe)}
                declarations = ','.join(f'${k}:ID!' for k in variables)
                fields = ' '.join(f'd{k}:deleteIssueComment(input:{{id:$id{k}}}){{clientMutationId}}' for k in range(len(safe)))
                time.sleep(1.1)
                try:
                    result = gh('graphql',{'query':f'mutation({declarations}){{{fields}}}','variables':variables})
                except RuntimeError as error:
                    if 'HTTP 504' not in str(error) or attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
                    check = gh('graphql', {'query': query, 'variables': {'ids': [c['node_id'] for c in safe]}})
                    if check.get('errors'): raise RuntimeError('Timeout readback failed; cleanup stopped')
                    remaining = {n['id']: n for n in check['data']['nodes'] if n}
                    retry = []
                    for c in safe:
                        node = remaining.get(c['node_id'])
                        if node is None: deleted.append(c['id'])
                        elif node['updatedAt'] == c['updated_at'] and digest(node['body'].encode()) == c['body_sha256']:
                            retry.append(c)
                        else: skipped.append(c['id'])
                    safe = retry
                    if not safe: break
                    continue
                for k,c in enumerate(safe):
                    if (result.get('data') or {}).get(f'd{k}') is not None: deleted.append(c['id'])
                if result.get('errors'): raise RuntimeError('GitHub rejected a deletion; stopped without retrying')
                break
            print(f'Archived comments removed: {len(deleted)}; preserved/skipped: {len(skipped)}',flush=True)
            time.sleep(1.1)
    finally:
        result={'deleted':deleted,'skipped':skipped,'source_snapshot':digest((CONTROL/'snapshot.json').read_bytes())}
        write(Path('knowledge-result.json'),encoded(result))
    remaining = all_pages(f'repos/{REPO}/issues/comments?per_page=100')
    issue_numbers={c['issue'] for c in candidates}
    result['remaining_issue_comments']=sum(int(c['issue_url'].rsplit('/',1)[1]) in issue_numbers for c in remaining)
    write(Path('knowledge-result.json'),encoded(result))
    return {k:len(v) if isinstance(v,list) else v for k,v in result.items()}


def event_capture(path: Path) -> dict:
    event=json.loads(path.read_text()); issue=event.get('issue')
    if not issue or 'pull_request' in issue: return {'ignored':'not an issue event'}
    number=issue['number']; store(number,'issue',issue)
    record=event.get('comment',issue); kind='comment' if 'comment' in event else 'issue'
    store(number,kind,record)
    previous=event.get('changes',{}).get('body',{}).get('from')
    if previous is not None:
        old=dict(record,body=previous,archive_note='Before-edit text supplied by GitHub event; its original update timestamp is not known.')
        store(number,kind,old)
    regenerate(number,issue)
    return {'captured_issue':number,'before_edit_preserved':previous is not None}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['archive','cleanup','event'])
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--event',type=Path)
    parser.add_argument('--exclude', type=int, action='append', default=[], help='Issue numbers excluded from this bulk archive/cleanup snapshot')
    args=parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY',REPO)!=REPO:raise RuntimeError('Wrong repository')
    result=archive(args.baseline, set(args.exclude)) if args.mode=='archive' else cleanup() if args.mode=='cleanup' else event_capture(args.event)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
