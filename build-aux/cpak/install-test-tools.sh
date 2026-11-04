#!/bin/sh
set -eu

# Keep runtime packages at their image versions while adding test tools.
dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' |
  awk '$2 == "installed" {print $1}' |
  xargs -r apt-mark hold > /dev/null
case "$(dpkg --print-architecture)" in
  amd64) mirror=https://archive.ubuntu.com/ubuntu/ ;;
  arm64) mirror=https://ports.ubuntu.com/ubuntu-ports/ ;;
  *) exit 1 ;;
esac
for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  test -f "$source" || continue
  sed -Ei "s|https?://snapshot\\.ubuntu\\.com/ubuntu(-ports)?/[0-9TZ]+/?|$mirror|g" "$source"
done
apt-get -o Acquire::Retries=5 --error-on=any update
exec apt-get -o Acquire::Retries=5 install -y --no-install-recommends "$@"
