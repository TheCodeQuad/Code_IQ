# CKG API Setup Instructions

## Environment Issue
The command execution environment has a PowerShell 6+ requirement issue. Use one of the following solutions:

## SOLUTION 1: Manual Creation (Windows Command Prompt)

Open Command Prompt (cmd.exe) and run:

```cmd
cd C:\BIA6\CodeIQ\Code_IQ

mkdir frontend\app\api\graphs\ckg
mkdir frontend\app\api\graphs\ckg\stats  
mkdir frontend\app\api\graphs\ckg\subgraph
```

Then create the files with the content shown below.

## SOLUTION 2: Using Node.js (Recommended)

```bash
cd C:\BIA6\CodeIQ\Code_IQ
node setup-ckg.js
```

This will automatically create all directories and files.

## SOLUTION 3: Using Python

```bash
cd C:\BIA6\CodeIQ\Code_IQ
python setup_ckg_simple.py
```

## File Locations and Content

### File 1: frontend\app\api\graphs\ckg\route.ts
[Content provided - see setup-ckg.js]

### File 2: frontend\app\api\graphs\ckg\stats\route.ts
[Content provided - see setup-ckg.js]

### File 3: frontend\app\api\graphs\ckg\subgraph\route.ts
[Content provided - see setup-ckg.js]

## Verification

After creation, verify with:
```cmd
dir /s C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg
```

Expected output:
- C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\route.ts
- C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\stats\route.ts
- C:\BIA6\CodeIQ\Code_IQ\frontend\app\api\graphs\ckg\subgraph\route.ts
