# USB Automation Tool

A command line utility for detecting removable drives, copying a directory to a selected drive, and verifying every transferred file with SHA-256. It records a manifest so the copy can be checked later. The default command is read-only; transfers require an explicit destination.

## Usage

```sh
python -m usb_tool list
python -m usb_tool copy ./photos E:/backup --dry-run
python -m usb_tool copy ./photos E:/backup
python -m usb_tool verify ./photos E:/backup
python -m unittest discover -s tests -v
```

`list` uses Windows drive type information or Linux mount metadata to identify removable volumes. A directory path can be used for testing without a USB device. The tool refuses source/destination overlap, symbolic links, duplicate target names, and paths outside the destination. It copies through a temporary file, flushes it, then replaces the target and verifies the digest. It never formats a drive: destructive formatting is deliberately a separate operating system operation.

## Requirements

Python 3.10+. No third-party packages.

