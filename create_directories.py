import os

# Create the directories
dirs = [
    r"C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg",
    r"C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\stats",
    r"C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\subgraph"
]

for dir_path in dirs:
    os.makedirs(dir_path, exist_ok=True)
    print(f"Created: {dir_path}")

# Verify by listing contents
graphs_dir = r"C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs"
print(f"\nContents of {graphs_dir}:")
for item in os.listdir(graphs_dir):
    item_path = os.path.join(graphs_dir, item)
    if os.path.isdir(item_path):
        print(f"  [DIR]  {item}")
        # List subdirectories of ckg if it exists
        if item == "ckg":
            ckg_path = os.path.join(graphs_dir, "ckg")
            for subitem in os.listdir(ckg_path):
                subitem_path = os.path.join(ckg_path, subitem)
                if os.path.isdir(subitem_path):
                    print(f"    [DIR]  {subitem}")
    else:
        print(f"  [FILE] {item}")
