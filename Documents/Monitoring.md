
**Monitoring Status / Troubleshooting**
The following command will allow status / errors to be traced during execution.
If troubleshooting, set `-verbose` in the config file.

`sudo SYSTEMD_LESS=RXMK /usr/bin/journalctl -f`

**Note:** There MAY be an issue with the PyGithub python module installing correcly.  This seemes to track to an older version of the OpenSSL libraries.
The following fixed the issue for me - I WOULD NOT TRY THIS UNLESS YOU REALLY KNOW WHAT YOU ARE DOING.
```
sudo rm -rf /usr/lib/python3/dist-packages/OpenSSL
sudo pip3 install pyOpenSSL
sudo pip3 install pyOpenSSL --upgrade
```