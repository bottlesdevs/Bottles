#!/usr/bin/env python3
"""Quick test to verify path normalization logic."""

# Test the regex-based normalization
def test_normalize_path():
    import re
    
    test_cases = [
        # (input_path, expected_output)
        ("C:\\Program Files\\game.exe", "C:\\Program Files\\game.exe"),  # Already Windows
        ("/var/home/user/.local/share/bottles/bottles/MyBottle/drive_c/Program Files/game.exe", "C:\\Program Files\\game.exe"),
        ("/path/to/bottle/drive_d/Games/game.exe", "D:\\Games\\game.exe"),
        ("/path/dosdevices/c:/windows/system32/cmd.exe", "C:\\windows\\system32\\cmd.exe"),
        ("/path/dosdevices/e:/data/file.txt", "E:\\data\\file.txt"),
    ]
    
    def normalize(program_path: str) -> str:
        """Simplified version of _normalize_path_to_windows."""
        # Already Windows format?
        if ":" in program_path and "\\" in program_path:
            return program_path
        
        # Convert Unix path to Windows format
        if "/drive_" in program_path:
            match = re.search(r"drive_([a-z])/(.+)", program_path)
            if match:
                drive = match.group(1).upper()
                rest = match.group(2).replace("/", "\\")
                return f"{drive}:\\{rest}"
        elif "/dosdevices/" in program_path:
            match = re.search(r"dosdevices/([a-z]):/(.+)", program_path)
            if match:
                drive = match.group(1).upper()
                rest = match.group(2).replace("/", "\\")
                return f"{drive}:\\{rest}"
        
        return program_path
    
    print("Testing path normalization:")
    print("-" * 80)
    
    all_passed = True
    for input_path, expected in test_cases:
        result = normalize(input_path)
        passed = result == expected
        all_passed = all_passed and passed
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}")
        print(f"  Input:    {input_path}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")
        print()
    
    print("-" * 80)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = test_normalize_path()
    sys.exit(0 if success else 1)
