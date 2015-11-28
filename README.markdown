# Qubes OS Userbase Estimator

This is the script that powers official Qubes OS user counter. It searches the
httpd logfile for downloads of the repo index files (`repomd.xml`) and counts
unique IP addresses which access those files. Based on that, the statistics are
shown.

![Official statistics](https://ftp.qubes-os.org/~woju/counter/stats.svg)
