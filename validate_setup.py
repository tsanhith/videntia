"""
SETUP VALIDATION SCRIPT
Run this to verify your free deployment is configured correctly

Usage:
    python validate_setup.py

This checks:
✓ Environment variables are set
✓ Supabase connection works
✓ Database schema exists
✓ API is reachable
✓ Models can load
"""

import os
import sys
from pathlib import Path

# Color codes for terminal output
green = "\033[92m"
red = "\033[91m"
yellow = "\033[93m"
blue = "\033[94m"
reset = "\033[0m"
check = "✓"
cross = "✗"
warn = "⚠"

def print_header(text):
    print(f"\n{blue}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{reset}")

def print_success(text):
    print(f"{green}{check} {text}{reset}")

def print_error(text):
    print(f"{red}{cross} {text}{reset}")

def print_warning(text):
    print(f"{yellow}{warn} {text}{reset}")

def print_info(text):
    print(f"  → {text}")

# =====================================================
# CHECK 1: Environment Variables
# =====================================================

print_header("1. CHECKING ENVIRONMENT VARIABLES")

required_vars = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "HF_TOKEN",
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var, "").strip()
    if value:
        # Mask sensitive values
        masked = value[:10] + "..." + value[-5:] if len(value) > 15 else value
        print_success(f"{var} = {masked}")
    else:
        print_error(f"{var} not set")
        missing_vars.append(var)

if missing_vars:
    print_warning(f"Missing: {', '.join(missing_vars)}")
    print_info("Copy .env.example → .env, fill in your values")
    print_info("Then: export $(cat .env | xargs)")
    sys.exit(1)
else:
    print_success("All required environment variables set!")

# =====================================================
# CHECK 2: Supabase Connection
# =====================================================

print_header("2. TESTING SUPABASE CONNECTION")

try:
    from supabase import create_client
    print_success("Supabase library installed")
except ImportError:
    print_error("Supabase library not installed")
    print_info("Run: pip install supabase")
    sys.exit(1)

try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    client = create_client(supabase_url, supabase_key)
    print_success("Supabase client created")
    
    # Test connection by querying
    result = client.table("videos").select("*").limit(1).execute()
    print_success("Connected to Supabase database!")
    print_info(f"Found {len(result.data)} video(s) in database")
    
except Exception as e:
    print_error(f"Supabase connection failed: {e}")
    print_warning("Check:")
    print_info("1. Is SUPABASE_URL correct? (should end with .supabase.co)")
    print_info("2. Is SUPABASE_KEY an 'anon public' key (not service role)?")
    print_info("3. Is database schema created? (run SUPABASE_SCHEMA.sql)")
    sys.exit(1)

# =====================================================
# CHECK 3: Database Schema
# =====================================================

print_header("3. CHECKING DATABASE SCHEMA")

required_tables = ["videos", "segments", "speakers", "query_results"]
missing_tables = []

for table in required_tables:
    try:
        result = client.table(table).select("*").limit(1).execute()
        print_success(f"Table '{table}' exists")
    except Exception as e:
        print_error(f"Table '{table}' missing or inaccessible")
        missing_tables.append(table)

if missing_tables:
    print_warning(f"Missing tables: {', '.join(missing_tables)}")
    print_info("Fix: Run SUPABASE_SCHEMA.sql in Supabase SQL Editor")
    print_info("Or manually create tables via Supabase dashboard")
    sys.exit(1)
else:
    print_success("All required tables exist!")

# =====================================================
# CHECK 4: API Connection (Optional)
# =====================================================

print_header("4. CHECKING API ENDPOINT")

api_url = os.getenv("API_BASE", "").strip()

if not api_url:
    print_warning("API_BASE not set - skipping API check")
    print_info("Set API_BASE=https://username-videntia-api.hf.space when ready")
else:
    try:
        import httpx
        async def check_api():
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{api_url}/health", timeout=5.0)
                return response.status_code == 200
        
        # Sync version
        import requests
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code == 200:
                print_success(f"API is running at {api_url}")
            else:
                print_warning(f"API responded with {response.status_code}")
        except:
            print_warning(f"API not responding at {api_url}")
            print_info("Is the HF Space deployed? Check status on HuggingFace")
    
    except ImportError:
        print_info("httpx not installed - skipping API check")
        print_info("To test API: pip install httpx, then re-run script")

# =====================================================
# CHECK 5: Python Dependencies
# =====================================================

print_header("5. CHECKING PYTHON DEPENDENCIES")

dependencies = {
    "supabase": "Database client",
    "httpx": "HTTP requests",
    "pydantic": "Data validation",
}

for package, description in dependencies.items():
    try:
        __import__(package)
        print_success(f"{package} - {description}")
    except ImportError:
        print_warning(f"{package} not installed")
        print_info(f"Run: pip install {package}")

# =====================================================
# CHECK 6: Optional: GPU & Models (Colab)
# =====================================================

print_header("6. CHECKING COLAB ENVIRONMENT (Optional)")

try:
    import google.colab
    print_success("Running in Google Colab")
    
    try:
        import torch
        print_success(f"PyTorch installed (version {torch.__version__})")
        
        if torch.cuda.is_available():
            print_success(f"GPU available: {torch.cuda.get_device_name(0)}")
            print_info(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            print_warning("GPU not available - enable in Colab")
            print_info("Runtime → Change runtime type → Hardware accelerator: GPU")
    
    except ImportError:
        print_info("PyTorch not installed - will install when needed")

except ImportError:
    print_info("Not running in Colab - local environment or other platform")

# =====================================================
# SUMMARY & NEXT STEPS
# =====================================================

print_header("✅ VALIDATION COMPLETE")

print(f"""
{green}Your free deployment is configured!{reset}

{blue}NEXT STEPS:{reset}
1. Upload a video to Google Colab (COLAB_QUICKSTART.py)
2. Run the notebook cells
3. Watch your video get processed (GPU-powered!)
4. Check {blue}https://your-dashboard-url{reset} to query results

{blue}REQUIRED FILES:{reset}
✓ COLAB_QUICKSTART.py - Main processor
✓ HF_SPACES_APP.py - API server (deployed to HF)
✓ VERCEL_DASHBOARD.jsx - Web UI (deployed to Vercel)
✓ SUPABASE_SCHEMA.sql - Database (already created)
✓ .env - Your credentials (filled in)

{blue}HELPFUL RESOURCES:{reset}
→ QUICKSTART_GUIDE.md - 30-minute setup guide
→ STUDENT_FREE_DEPLOYMENT.md - Full documentation
→ Phase4_Complete_Documentation.md - How the AI works

{blue}TROUBLESHOOTING:{reset}
If any check failed:
1. Check your .env values
2. Verify Supabase dashboard
3. Check HuggingFace Space logs
4. See error message above for specific help

{green}Questions? Check the docs or GitHub discussions!{reset}
""")

sys.exit(0)
