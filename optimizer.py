import subprocess
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from runner import run_solver
 
# ---------------- USER INPUTS ----------------
MEMORY = 999999999
# -------------------------------------------------
 
 
# 2️⃣ Parse elout
def parse_elout(elout_file, stress_limit):
    """Parse elout at specific timestep: 'at time 1.10000E+00'"""
    to_delete = []
    with open(elout_file, "r") as f:
        lines = f.readlines()

    # Step 1: find the line with the target timestep
    start_index = None
    for i, line in enumerate(lines):
        if "at time 1.10000E+00" in line:
            start_index = i + 5  # jump 5 lines after marker
            break

    if start_index is None:
        print("❌ Target time not found in elout.")
        return []

    # Step 2: read elements starting from start_index
    i = start_index
    while i < len(lines) - 1:
        lines[i]=lines[i].replace("-","")
        line1 = lines[i].split()
        line2 = lines[i + 1].split()
        try:
            eid = int(line1[0])             # element ID (line1, col1)
            stress = float(line2[7])        # effective stress (line2, col8)
            if stress < stress_limit:
                to_delete.append(eid)
        except (ValueError, IndexError):
            pass  # skip bad lines

        i += 2  # next element (2 lines per element)

    print(f"Parsed {len(to_delete)} low-stress elements at time 1.10000E+00.")
    return to_delete
 
 
# 3️⃣ Update k-file
def update_kfile(k_file, delete_ids, iteration):
    """
    Remove element IDs from:
    1. *ELEMENT_SOLID section (2 lines per element)
    2. *SET_SOLID section (8 EIDs per line, must collapse/shift)
    """
    base, ext = os.path.splitext(k_file)
    newfile = f"{base}_iter{iteration}{ext}"
    delete_ids_set = set(delete_ids)

    with open(k_file, "r") as fin, open(newfile, "w") as fout:
        inside_solid_block = False
        inside_set_block = False
        buffer_lines = []
        set_elements = []

        for line in fin:
            stripped = line.strip()

            # --- ELEMENT_SOLID block ---
            if stripped.startswith("*ELEMENT_SOLID"):
                inside_solid_block = True
                fout.write(line)
                continue

            if inside_solid_block:
                if stripped.startswith("*") and not stripped.startswith("*ELEMENT_SOLID"):
                    inside_solid_block = False
                    fout.write(line)
                    continue

                buffer_lines.append(line)

                if len(buffer_lines) == 2:
                    try:
                        eid = int(buffer_lines[0].split()[0])
                        if eid not in delete_ids_set:
                            fout.writelines(buffer_lines)
                    except ValueError:
                        fout.writelines(buffer_lines)
                    buffer_lines = []
                continue

            # --- SET_SOLID block ---
            if stripped.startswith("*SET_SOLID"):
                inside_set_block = True
                fout.write(line)
                header_count = 0
                continue

            if inside_set_block:
                if stripped.startswith("*") and not stripped.startswith("*SET_SOLID"):
                    inside_set_block = False
                    # Collapse set IDs and rewrite
                    set_elements = [eid for eid in set_elements if eid not in delete_ids_set]
                    for i in range(0, len(set_elements), 8):
                        fout.write("".join(f"{eid:10d}" for eid in set_elements[i:i+8]) + "\n")
                    set_elements = []
                    fout.write(line)
                    continue

                header_count += 1
                if header_count <= 3:
                    fout.write(line)
                else:
                    try:
                        ids = [int(x) for x in line.split()]
                        set_elements.extend(ids)
                    except ValueError:
                        pass
                continue

            # --- Default ---
            fout.write(line)

    return newfile
 
 
# 4️⃣ Optimization loop
def optimization_loop(k_file, solver, stress_limit, max_iter, ncpu):
    iteration = 0
    current_k = k_file
    elout_file = os.path.join(os.path.dirname(k_file), "elout")
 
    while iteration < max_iter:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")
 
        run_solver(current_k, solver, ncpu)
 
        if not os.path.exists(elout_file):
            print("❌ No elout produced. Stopping.")
            break
 
        to_delete = parse_elout(elout_file, stress_limit)
        print(f"Elements to delete this round: {len(to_delete)}")
 
        if not to_delete:
            print("✅ No more elements below stress limit. Optimization complete.")
            break
 
        # Backup current k-file
        shutil.copy(current_k, f"backup_before_iter{iteration}.k")
 
        # Update k-file for next run
        current_k = update_kfile(current_k, to_delete, iteration)
        print(f"Updated k-file: {current_k}")
 
    print("\n🏁 Optimization finished.")

def browse_kfile():
    filename = filedialog.askopenfilename(filetypes=[("LS-DYNA K files", "*.k")])
    if filename:
        k_file_var.set(filename)

def browse_solver():
    filename = filedialog.askopenfilename(filetypes=[("Executables", "*.exe")])
    if filename:
        solver_var.set(filename)

def run_from_gui():
    try:
        k_file = k_file_var.get()
        solver = solver_var.get()
        stress_limit = float(stress_limit_var.get())
        max_iter = int(max_iter_var.get())
        ncpu = int(ncpu_var.get())

        if not os.path.exists(k_file):
            messagebox.showerror("Error", "Invalid K-file path")
            return
        if not os.path.exists(solver):
            messagebox.showerror("Error", "Invalid solver path")
            return

        def run_thread():
            messagebox.showinfo("Running", "Optimization started… check console output")
            optimization_loop(k_file, solver, stress_limit, max_iter, ncpu)

        threading.Thread(target=run_thread).start()

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ---------------- GUI ----------------
root = tk.Tk()
root.title("LS-DYNA Weight Optimizer")

k_file_var = tk.StringVar()
solver_var = tk.StringVar()
stress_limit_var = tk.StringVar(value="50")
max_iter_var = tk.StringVar(value="20")
ncpu_var = tk.StringVar(value="16")

# Row 1: K file
tk.Label(root, text="K file:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
tk.Entry(root, textvariable=k_file_var, width=50).grid(row=0, column=1, padx=5)
tk.Button(root, text="Browse", command=browse_kfile).grid(row=0, column=2, padx=5)

# Row 2: Solver exe
tk.Label(root, text="Solver exe:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
tk.Entry(root, textvariable=solver_var, width=50).grid(row=1, column=1, padx=5)
tk.Button(root, text="Browse", command=browse_solver).grid(row=1, column=2, padx=5)

# Row 3: Stress limit
tk.Label(root, text="Stress limit:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
tk.Entry(root, textvariable=stress_limit_var, width=10).grid(row=2, column=1, sticky="w", padx=5)

# Row 4: Max iterations
tk.Label(root, text="Max iterations:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
tk.Entry(root, textvariable=max_iter_var, width=10).grid(row=3, column=1, sticky="w", padx=5)

# Row 5: NCPU
tk.Label(root, text="NCPU:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
tk.Entry(root, textvariable=ncpu_var, width=10).grid(row=4, column=1, sticky="w", padx=5)

# Run button
tk.Button(root, text="Run Optimization", command=run_from_gui, bg="lightgreen").grid(row=5, column=1, pady=15)

root.mainloop()