import subprocess
# 1️⃣ Run solver
def run_solver(k_file, solver, ncpu):
    cmd = f'"{solver}" i={k_file} ncpu={ncpu} memory={MEMORY}'
    print(f"⚡ Running solver: {cmd}")
    subprocess.run(cmd, shell=True)