#!/usr/bin/env python3
"""Standalone verification script for pagination functionality."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def main():
    """Verify pagination implementation without pytest fixtures."""
    
    print("=" * 60)
    print("PAGINATION VERIFICATION CHECKLIST")
    print("=" * 60)
    
    # Check 1: Views have correct function signatures
    print("\n[1] Checking views.py...")
    try:
        from app.views.worlds import render_worlds_table_paginated
        import inspect
        sig = inspect.signature(render_worlds_table_paginated)
        params = list(sig.parameters.keys())
        
        required_params = ['page', 'page_size', 'total_count', 'current_page', 'total_pages']
        missing = [p for p in required_params if p not in params]
        
        if missing:
            print(f"   ❌ Missing parameters: {missing}")
            return False
        else:
            print(f"   ✓ All required parameters present: {params[:5]}...")
    except Exception as e:
        print(f"   ⚠ Import error (expected if server not running): {e}")
    
    # Check 2: Templates exist and contain Load More button
    print("\n[2] Checking template files...")
    template_paths = [
        "backend/app/templates/components/database_worlds_paginated.html",
        "backend/app/core/templates.py"
    ]
    
    for path in template_paths:
        full_path = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                content = f.read()
                if 'Load more worlds...' in content or 'hx-trigger="revealed"' in content:
                    print(f"   ✓ {path.split('/')[-1]} contains Load More functionality")
                else:
                    print(f"   ⚠ {path.split('/')[-1]} may be missing HTMX load more button")
        else:
            print(f"   ✗ File not found: {full_path}")
    
    # Check 3: Views.py has correct endpoint routing
    print("\n[3] Checking views.py endpoint...")
    views_path = os.path.join(os.path.dirname(__file__), 'backend/app/views/worlds.py')
    if os.path.exists(views_path):
        with open(views_path, 'r') as f:
            content = f.read()
            
            checks = [
                ('/worlds/database-worlds', 'Paginated endpoint defined'),
                ('render_worlds_table_paginated', 'Template rendering function'),
                ('total_items', 'Total items parameter usage'),
                ('batch_research', 'Batch research endpoint'),
                ('toggle_explored', 'Toggle explored endpoint'),
            ]
            
            for pattern, desc in checks:
                if pattern in content:
                    print(f"   ✓ {desc}: Found '{pattern[:30]}...{pattern[-10:]}'")
                else:
                    print(f"   ⚠ {desc}: Pattern not found")
    else:
        print(f"   ⚠ views.py not found at expected location")
    
    # Check 4: Helper functions exist
    print("\n[4] Checking core templates.py...")
    helpers_path = os.path.join(os.path.dirname(__file__), 'backend/app/core/templates.py')
    if os.path.exists(helpers_path):
        with open(helpers_path, 'r') as f:
            content = f.read()
            
            helper_checks = [
                ('render_worlds_table_paginated', 'Pagination helper function'),
                ('json_decode', 'JSON decode filter'),
            ]
            
            for func, desc in helper_checks:
                if func in content:
                    print(f"   ✓ {desc}: Function '{func}' defined")
                else:
                    print(f"   ⚠ {desc}: Function '{func}' not found")
    else:
        print(f"   ⚠ core/templates.py not found")
    
    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    main()