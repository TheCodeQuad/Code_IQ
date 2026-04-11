import os

# Create the required directories
directories = [
    r'C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg',
    r'C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\stats',
    r'C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\subgraph'
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Created: {directory}")

print("All directories created successfully!")
