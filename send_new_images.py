#!/usr/bin/env python3
"""
send_new_images.py

Scans a monitor directory for new image files and sends them as attachments via SMTP.
Features added:
- Automatic splitting of attachments into multiple emails when total size exceeds a configured limit.
- Dry-run mode to simulate sending and DB updates without performing them.

Environment variables / CLI options:
- EMAIL_USER (required) or --user
- EMAIL_PASS (required) or --password
- SMTP_SERVER (default smtp.gmail.com)
- SMTP_PORT (default 587)
- EMAIL_TO (default hi@returnright.sg)
- MONITOR_DIR (default /home/jordanaw/Nextcloud/returnright-db)
- ATTACHMENT_SIZE_LIMIT (bytes, default 25165824 = 24 * 1024 * 1024)

CLI flags:
- --dry-run  : do everything except actually sending emails and updating .sent_images.json

Behavior:
- Groups new images into batches where the sum of sizes for each batch <= ATTACHMENT_SIZE_LIMIT.
- If a single image is larger than the limit, it is sent alone with a warning.
- After successfully sending each batch, the script records sent images in .sent_images.json.

"""

import os
import sys
import json
import time
import argparse
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import List, Tuple

DEFAULT_MONITOR = '/home/jordanaw/Nextcloud/returnright-db'
SENT_DB_NAME = '.sent_images.json'
BODY_FILE_NAME = 'email-content.txt'
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp', '.webp', '.heic'}
DEFAULT_SIZE_LIMIT = 24 * 1024 * 1024  # 24 MB


def load_sent_db(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            # If corrupted, back it up and start fresh
            bak = path.with_name(path.name + '.bak')
            path.rename(bak)
            print(f"Warning: corrupted sent DB moved to {bak}")
            return {}
    return {}


def save_sent_db(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def is_image_file(p: Path):
    if not p.is_file():
        return False
    return p.suffix.lower() in IMAGE_EXTS


def find_new_images(monitor_dir: Path, sent_db: dict) -> List[Tuple[Path, int, int]]:
    candidates = []
    for entry in monitor_dir.iterdir():
        if entry.name in {SENT_DB_NAME, BODY_FILE_NAME}:
            continue
        if is_image_file(entry):
            stat = entry.stat()
            mtime = int(stat.st_mtime)
            size = stat.st_size
            key = entry.name
            prev = sent_db.get(key)
            if prev is None:
                candidates.append((entry, mtime, size))
            else:
                # If file changed (mtime or size) treat as new
                if prev.get('mtime') != mtime or prev.get('size') != size:
                    candidates.append((entry, mtime, size))
    # Sort for deterministic order
    candidates.sort(key=lambda t: t[0].name)
    return candidates


def read_email_body(monitor_dir: Path):
    body_path = monitor_dir / BODY_FILE_NAME
    if body_path.exists():
        return body_path.read_text(encoding='utf-8')
    return ''


def attach_file(msg: EmailMessage, file_path: Path):
    ctype, encoding = mimetypes.guess_type(str(file_path))
    if ctype is None:
        maintype, subtype = 'application', 'octet-stream'
    else:
        maintype, subtype = ctype.split('/', 1)
    with open(file_path, 'rb') as f:
        data = f.read()
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=file_path.name)


def send_email(smtp_server, smtp_port, user, password, msg: EmailMessage):
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=60) as server:
            server.ehlo()
            if smtp_port == 587:
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.send_message(msg)
    except Exception:
        raise


def chunk_images_by_size(items: List[Tuple[Path, int, int]], size_limit: int) -> List[List[Tuple[Path, int, int]]]:
    """Group images into batches where sum(size) <= size_limit.
    A single image larger than size_limit will be placed in its own batch.
    """
    batches: List[List[Tuple[Path, int, int]]] = []
    current: List[Tuple[Path, int, int]] = []
    current_size = 0

    for item in items:
        _, _, sz = item
        if current and (current_size + sz) > size_limit:
            batches.append(current)
            current = []
            current_size = 0

        if sz > size_limit:
            # image itself exceeds limit: send alone
            if current:
                batches.append(current)
                current = []
                current_size = 0
            batches.append([item])
        else:
            current.append(item)
            current_size += sz

    if current:
        batches.append(current)
    return batches


def build_message(user: str, to: str, subject: str, body: str, batch: List[Tuple[Path, int, int]]) -> EmailMessage:
    msg = EmailMessage()
    msg['From'] = user
    msg['To'] = to
    msg['Subject'] = subject
    if body.strip():
        msg.set_content(body)
    else:
        msg.set_content('Please see attached images.')

    for p, _, _ in batch:
        attach_file(msg, p)
    return msg


def main():
    parser = argparse.ArgumentParser(description='Send new images from monitor dir via email')
    parser.add_argument('--monitor-dir', default=os.environ.get('MONITOR_DIR', DEFAULT_MONITOR))
    parser.add_argument('--to', default=os.environ.get('EMAIL_TO', 'hi@returnright.sg'))
    parser.add_argument('--smtp-server', default=os.environ.get('SMTP_SERVER', 'smtp.gmail.com'))
    parser.add_argument('--smtp-port', type=int, default=int(os.environ.get('SMTP_PORT', '587')))
    parser.add_argument('--user', default=os.environ.get('EMAIL_USER'))
    parser.add_argument('--password', default=os.environ.get('EMAIL_PASS'))
    parser.add_argument('--size-limit', type=int, default=int(os.environ.get('ATTACHMENT_SIZE_LIMIT', str(DEFAULT_SIZE_LIMIT))))
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without sending emails or updating the sent DB')
    args = parser.parse_args()

    monitor_dir = Path(args.monitor_dir)
    if not monitor_dir.exists() or not monitor_dir.is_dir():
        print(f"Error: monitor dir {monitor_dir} does not exist or is not a directory", file=sys.stderr)
        sys.exit(2)

    user = args.user
    password = args.password
    if not user or not password:
        print("Error: EMAIL_USER and EMAIL_PASS environment variables must be set (or pass --user/--password)", file=sys.stderr)
        sys.exit(3)

    sent_db_path = monitor_dir / SENT_DB_NAME
    sent_db = load_sent_db(sent_db_path)

    new_images = find_new_images(monitor_dir, sent_db)
    if not new_images:
        print("No new images to send.")
        sys.exit(0)

    body = read_email_body(monitor_dir)
    base_subject = f"Refund receipt claim ({time.strftime('%Y-%m-%d %H:%M:%S')})"

    # Partition into batches
    size_limit = args.size_limit
    batches = chunk_images_by_size(new_images, size_limit)

    total_images = sum(len(b) for b in batches)
    print(f"Found {len(new_images)} new image(s) across {len(batches)} batch(es); size limit = {size_limit} bytes")

    # Dry-run: simulate sends and DB updates
    if args.dry_run:
        for idx, batch in enumerate(batches, start=1):
            batch_size = sum(sz for _, _, sz in batch)
            names = [p.name for p, _, _ in batch]
            subj = base_subject
            if len(batches) > 1:
                subj = f"{base_subject} (part {idx}/{len(batches)})"
            print(f"[DRY-RUN] Would send email to {args.to} with subject: '{subj}' and {len(batch)} attachment(s) (total {batch_size} bytes): {names}")
        print("[DRY-RUN] Would update sent DB for these images.")
        sys.exit(0)

    # Real send: iterate batches, send and update DB per successful batch
    now = int(time.time())
    sent_count = 0
    for idx, batch in enumerate(batches, start=1):
        batch_size = sum(sz for _, _, sz in batch)
        names = [p.name for p, _, _ in batch]
        subj = base_subject
        if len(batches) > 1:
            subj = f"{base_subject} (part {idx}/{len(batches)})"

        if batch_size > size_limit:
            print(f"Warning: batch {idx} total size {batch_size} exceeds limit {size_limit} bytes; attempting to send anyway.")

        msg = build_message(user, args.to, subj, body, batch)
        try:
            send_email(args.smtp_server, args.smtp_port, user, password, msg)
        except Exception as e:
            print(f"Error sending batch {idx}: {e}", file=sys.stderr)
            sys.exit(4)

        # mark sent images in DB and persist
        for p, mtime, size in batch:
            sent_db[p.name] = {'mtime': mtime, 'size': size, 'sent_at': now}
            sent_count += 1
        try:
            save_sent_db(sent_db_path, sent_db)
        except Exception as e:
            print(f"Warning: failed to update sent DB after batch {idx}: {e}", file=sys.stderr)

        print(f"Sent batch {idx}/{len(batches)}: {len(batch)} image(s) to {args.to}")

    print(f"Done. Sent {sent_count} image(s) in {len(batches)} message(s) to {args.to}.")


if __name__ == '__main__':
    main()
