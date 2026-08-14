# tools/audit_scanner.py

import os
import re
import json
from collections import defaultdict

# Project roots to scan
TARGET_DIRS = ["core", "modules", "ui", "app.py"]

class SystemScanner:
    def __init__(self):
        self.report = {
            "missing_init_files": [],
            "internal_imports": defaultdict(list),
            "suspicious_ghost_imports": []
        }
        # Known split-brain signatures
        self.ghost_signatures = [
            "core.service.exceptions", 
            "ArchitectureViolationError"
        ]

    def scan(self):
        print("[*] Starting SIMS v2.2 MRI Scan...")
        
        for target in TARGET_DIRS:
            if not os.path.exists(target):
                continue
                
            if os.path.isfile(target):
                self._analyze_file(target)
                continue

            for root, dirs, files in os.walk(target):
                # 1. Check for missing __init__.py (Crucial for Python Packages)
                if "__pycache__" not in root and root != target:
                    if "__init__.py" not in files:
                        self.report["missing_init_files"].append(root)

                # 2. Analyze Python files for Split Brain imports
                for file in files:
                    if file.endswith(".py"):
                        self._analyze_file(os.path.join(root, file))
        
        self._generate_report()

    def _analyze_file(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                content = f.readlines()
                for line_num, line in enumerate(content, 1):
                    line = line.strip()
                    
                    # Track internal dependencies
                    if line.startswith("import modules.") or line.startswith("from modules.") or \
                       line.startswith("import core.") or line.startswith("from core.") or \
                       line.startswith("import ui.") or line.startswith("from ui."):
                        
                        self.report["internal_imports"][filepath].append(line)
                        
                        # Flag known split-brain signatures immediately
                        for ghost in self.ghost_signatures:
                            if ghost in line:
                                self.report["suspicious_ghost_imports"].append({
                                    "file": filepath,
                                    "line": line_num,
                                    "code": line,
                                    "issue": f"Contains potential ghost signature: '{ghost}'"
                                })
            except Exception as e:
                print(f"[!] Error reading {filepath}: {e}")

    def _generate_report(self):
        report_path = "audit_report.json"
        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=4)
        
        print("\n" + "="*50)
        print("🔍 AUDIT SCAN COMPLETE")
        print("="*50)
        print(f"Missing __init__.py files : {len(self.report['missing_init_files'])}")
        print(f"Suspicious Ghost Imports  : {len(self.report['suspicious_ghost_imports'])}")
        print(f"\nDetailed report generated at: {report_path}")
        print("Please hand this report over to CA Sahab for architectural analysis.")

if __name__ == "__main__":
    scanner = SystemScanner()
    scanner.scan()# tools/audit_scanner.py

import os
import re
import json
from collections import defaultdict

# Project roots to scan
TARGET_DIRS = ["core", "modules", "ui", "app.py"]

class SystemScanner:
    def __init__(self):
        self.report = {
            "missing_init_files": [],
            "internal_imports": defaultdict(list),
            "suspicious_ghost_imports": []
        }
        # Known split-brain signatures
        self.ghost_signatures = [
            "core.service.exceptions", 
            "ArchitectureViolationError"
        ]

    def scan(self):
        print("[*] Starting SIMS v2.2 MRI Scan...")
        
        for target in TARGET_DIRS:
            if not os.path.exists(target):
                continue
                
            if os.path.isfile(target):
                self._analyze_file(target)
                continue

            for root, dirs, files in os.walk(target):
                # 1. Check for missing __init__.py (Crucial for Python Packages)
                if "__pycache__" not in root and root != target:
                    if "__init__.py" not in files:
                        self.report["missing_init_files"].append(root)

                # 2. Analyze Python files for Split Brain imports
                for file in files:
                    if file.endswith(".py"):
                        self._analyze_file(os.path.join(root, file))
        
        self._generate_report()

    def _analyze_file(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                content = f.readlines()
                for line_num, line in enumerate(content, 1):
                    line = line.strip()
                    
                    # Track internal dependencies
                    if line.startswith("import modules.") or line.startswith("from modules.") or \
                       line.startswith("import core.") or line.startswith("from core.") or \
                       line.startswith("import ui.") or line.startswith("from ui."):
                        
                        self.report["internal_imports"][filepath].append(line)
                        
                        # Flag known split-brain signatures immediately
                        for ghost in self.ghost_signatures:
                            if ghost in line:
                                self.report["suspicious_ghost_imports"].append({
                                    "file": filepath,
                                    "line": line_num,
                                    "code": line,
                                    "issue": f"Contains potential ghost signature: '{ghost}'"
                                })
            except Exception as e:
                print(f"[!] Error reading {filepath}: {e}")

    def _generate_report(self):
        report_path = "audit_report.json"
        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=4)
        
        print("\n" + "="*50)
        print("🔍 AUDIT SCAN COMPLETE")
        print("="*50)
        print(f"Missing __init__.py files : {len(self.report['missing_init_files'])}")
        print(f"Suspicious Ghost Imports  : {len(self.report['suspicious_ghost_imports'])}")
        print(f"\nDetailed report generated at: {report_path}")
        print("Please hand this report over to CA Sahab for architectural analysis.")

if __name__ == "__main__":
    scanner = SystemScanner()
    scanner.scan()
