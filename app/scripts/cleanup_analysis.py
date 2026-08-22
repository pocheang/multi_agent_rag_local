"""
Cleanup script for high-priority fixes analysis files.

Run after reviewing the fixes to remove temporary analysis files.
"""

from pathlib import Path


def cleanup_analysis_files():
    """Remove temporary analysis files."""
    files_to_remove = [
        "temp_constants.txt",
        "config_usage_analysis.txt",
    ]

    removed = []
    not_found = []

    for filename in files_to_remove:
        filepath = Path(filename)
        if filepath.exists():
            filepath.unlink()
            removed.append(filename)
            print(f"✓ Removed: {filename}")
        else:
            not_found.append(filename)
            print(f"⚠ Not found: {filename}")

    return removed, not_found


def main():
    print("=" * 70)
    print("CLEANUP: High Priority Fixes - Analysis Files")
    print("=" * 70)
    print()

    removed, not_found = cleanup_analysis_files()

    print()
    print("Summary:")
    print(f"  - Removed: {len(removed)} files")
    print(f"  - Not found: {len(not_found)} files")
    print()

    if removed:
        print("Cleaned up temporary analysis files.")
    else:
        print("No files to clean up (already removed or not in current directory).")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
