import os

# Get the path to the actual main.py
main_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "main.py")
print(f"Main.py path: {main_file}")

# Recreate the path calculation from main.py
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(main_file))), "frontend")
print(f"Calculated frontend directory: {frontend_dir}")

# Check if the directory exists
if os.path.exists(frontend_dir):
    print(f"Frontend directory exists: {frontend_dir}")
    # Check if index.html exists
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        print(f"index.html exists: {index_path}")
        # Check file size
        size = os.path.getsize(index_path)
        print(f"index.html size: {size} bytes")
    else:
        print(f"index.html does NOT exist in: {frontend_dir}")
else:
    print(f"Frontend directory does NOT exist: {frontend_dir}")

# List files in the calculated directory
print("\nFiles in frontend directory:")
if os.path.exists(frontend_dir):
    for file in os.listdir(frontend_dir):
        print(f"  {file}")
