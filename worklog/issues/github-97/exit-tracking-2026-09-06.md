# Windows exit-tracking correction

Continuation request (verbatim): "Yeah it does that sometimes. Try again. Do everything. If you can otherwise you can just immediately stop and notif me"

GitHub connectivity recovered. Inspected final PR head 39106fb and failed Windows job 101500350417 in run 34038314113. Native module selection and Play/Stop assertions passed; immediate TemporaryDirectory cleanup failed with WinError 32. The production controller considered an empty job PID list sufficient proof of full exit.

Retain primary and observed child process handles until WaitForSingleObject signals termination. Verify IsProcessInJob after opening a child handle so PID reuse cannot transfer ownership. Pin children before TerminateJobObject, keep pending exits visible to Stop, and release each handle exactly once. Invalid waits now raise instead of being treated as running indefinitely or as successful waits.

Added deterministic membership/exit, wait-failure and wait-timeout cases; the first two fail against the original source. Added a Windows-only twelve-cycle real-process working-directory-release test with no cleanup retry or ignored errors. Local result: 42 Warband tests (6 Windows skips), 7 coverage tests and Node graph regressions passed. Windows and browser CI must pass before merge; no real game test is claimed.

Primary Win32 references: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject and https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess . Termination is asynchronous; process wait state, not the return of the termination call, proves exit.

Current candidate a5cec900 and master e4d292815 merge cleanly in git merge-tree. Preserve the parallel source archives and use a normal, non-forced PR merge after verifying the final merge candidate.
