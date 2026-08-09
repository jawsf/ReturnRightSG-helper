ReturnRight: Send new images by email

This repository contains a small utility that monitors a folder for new image files and sends them as attachments in a single email. It is intended to be used with a Gmail account (using an app password) but can be configured for any SMTP server.

Files
- [send_new_images.sh](/home/jordanaw/Repos/returnright/send_new_images.sh) — Bash wrapper that sources environment variables (if present) and calls the Python sender.
- [send_new_images.py](/home/jordanaw/Repos/returnright/send_new_images.py) — Python script that scans the monitored folder, reads email text from email-content.txt, attaches new images and sends them via SMTP. It records sent images in a small JSON database so images are not re-sent.
- [send_env.sh](/home/jordanaw/Repos/returnright/send_env.sh) — Template for sensitive environment variables. DO NOT commit this file; populate it with real credentials and protect its permissions.

Monitored folder (default)
- /home/jordanaw/Nextcloud/returnright-db

Inside the monitored folder the script expects (optional):
- email-content.txt — plain-text email body used for the message. If absent, a default short message is used.
- .sent_images.json — internal file created/updated by the script to track which images have already been sent. Do not edit manually unless you know what you're doing.

Environment variables
Provide sensitive settings in a local file next to the scripts: /home/jordanaw/Repos/returnright/send_env.sh
Example contents (edit and uncomment values):

# export EMAIL_USER="yourgmail@gmail.com"
# export EMAIL_PASS="your_gmail_app_password"
# export SMTP_SERVER="smtp.gmail.com"
# export SMTP_PORT="587"
# export EMAIL_TO="hi@returnright.sg"
# export MONITOR_DIR="/home/jordanaw/Nextcloud/returnright-db"
# export ATTACHMENT_SIZE_LIMIT="25165824"  # size limit in bytes (default 24MB). When exceeded, attachments are split across multiple emails.

The script supports a --dry-run flag to simulate sending and DB updates without performing them:

python3 send_new_images.py --dry-run

This is useful for testing which images would be sent and how they are batched.

Security notes
- Use a Gmail app password (recommended) instead of your main account password. Create an app password in Google Account > Security > App passwords.
- Set restricted file permissions on send_env.sh: chmod 600 send_env.sh
- Add send_env.sh to your .gitignore (if using git) to avoid accidentally committing it:
  echo "send_env.sh" >> .gitignore

Make the wrapper executable

chmod +x /home/jordanaw/Repos/returnright/send_new_images.sh

Basic usage

1. Create and populate /home/jordanaw/Repos/returnright/send_env.sh with your EMAIL_USER and EMAIL_PASS (and any optional overrides), then secure it with chmod 600.
2. Populate the monitored folder /home/jordanaw/Nextcloud/returnright-db with images and an optional email-content.txt file.
3. Run the wrapper:

/home/jordanaw/Repos/returnright/send_new_images.sh

Or run the Python script directly with overrides:

python3 /home/jordanaw/Repos/returnright/send_new_images.py --monitor-dir /home/jordanaw/Nextcloud/returnright-db --to hi@returnright.sg

Scheduling with cron (example)

Run every 5 minutes (edit crontab with crontab -e):

*/5 * * * * EMAIL_USER=you@gmail.com EMAIL_PASS=app_password /home/jordanaw/Repos/returnright/send_new_images.sh >> /var/log/send_new_images.log 2>&1

Or source the env file inside the cron job and run the script:

*/5 * * * * . /home/jordanaw/Repos/returnright/send_env.sh && /home/jordanaw/Repos/returnright/send_new_images.sh >> /var/log/send_new_images.log 2>&1

Systemd timer (optional)

Create a systemd service and timer pair if you prefer timers over cron. The service should run the wrapper script. Keep the environment file outside of version control and reference it in the service unit with EnvironmentFile=.

Important behavior and limitations
- The script records sent images in the monitor folder as .sent_images.json (filename and metadata). Images already recorded are not re-sent unless the file changes (mtime or size changes), in which case the image is considered new again.
- Attachments are grouped into batches so each email's total attachments do not exceed ATTACHMENT_SIZE_LIMIT (default 24MB). If the total size of new images exceeds the limit they will be sent in multiple messages, each with its own subject annotated with part numbers when applicable.
- If a single image file is larger than the configured size limit, it will be sent alone in its own email (a warning is emitted).
- Use --dry-run to simulate sending and DB updates without performing them.

Troubleshooting
- SMTP authentication errors: verify EMAIL_USER and EMAIL_PASS (use an app password for Gmail). Check that your Google account allows SMTP (app passwords or appropriate security settings required).
- Connection errors: verify SMTP_SERVER and SMTP_PORT (defaults: smtp.gmail.com:587). Ensure network/ firewall allows outbound SMTP connections.
- Large attachments: if the send fails due to size limits, reduce the number or size of images or implement splitting into multiple emails.
- No images sent: ensure new images are actual files with supported extensions (.jpg/.jpeg/.png/.gif/.tiff/.bmp/.webp/.heic) and they are not already recorded in .sent_images.json.

Extending the utility
- Replace username/password SMTP with OAuth2 for Gmail to avoid using app passwords.
- Add logging to a file or integrate with a system logging facility.
- Create systemd service and timer unit files (examples can be provided) for more robust scheduling and logging.

Support
If you want any of the extensions above (dry-run, splitting, OAuth2 integration, logging to file instead of stdout, or systemd timer examples), ask and a change can be made.
