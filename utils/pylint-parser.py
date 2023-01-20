import sys
import subprocess

git_diff_raw = subprocess.run("git diff --name-only origin/main | grep \"\.py$\"", capture_output=True, shell=True, check=False)

git_diff = git_diff_raw.stdout.decode("ascii").splitlines()

if len(git_diff) == 0:
    sys.exit(0)

pylint_result = subprocess.run("pylint bottles", capture_output=True, shell=True, check=False)

should_print = False
for l in pylint_result.stdout.decode("ascii").splitlines():
    if l.startswith("******"):
        file_name = l.split("************* Module ")[1].replace(".", "/") + ".py"
        should_print = file_name in git_diff

    if should_print:
        if "E1101: Instance of 'Child' has no " in l:
            continue
        if "E0602: Undefined variable '_' (undefined-variable)" in l:
            continue
        print(l)
