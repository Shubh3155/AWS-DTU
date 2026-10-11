#!/usr/bin/env bash
# Run on the Ubuntu host after uploading the exact image and private env file.
set -euo pipefail
release_dir=$1
release_sha=$2
[[ "$release_sha" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ "$release_dir" == "$HOME"/aeroroute/releases/"$release_sha" ]] || exit 2
exec 9>"$HOME/aeroroute/deploy.lock"
flock -n 9 || { echo 'Another deployment is active'; exit 1; }
chmod 600 "$release_dir/release.env"
sudo docker load --input "$release_dir/image.tar.gz" >/dev/null
image="aeroroute-api:$release_sha"
sudo docker image inspect "$image" >/dev/null
old_name="aeroroute-api-previous"
sudo docker rm -f "$old_name" >/dev/null 2>&1 || true
if sudo docker inspect aeroroute-api >/dev/null 2>&1; then
  sudo docker stop aeroroute-api >/dev/null
  sudo docker rename aeroroute-api "$old_name"
fi
rollback() {
  sudo docker rm -f aeroroute-api >/dev/null 2>&1 || true
  if sudo docker inspect "$old_name" >/dev/null 2>&1; then
    sudo docker rename "$old_name" aeroroute-api
    sudo docker start aeroroute-api >/dev/null
  fi
  echo 'Release failed; previous container restored where available.'
}
trap rollback ERR
sudo docker run --detach --name aeroroute-api --restart unless-stopped \
  --security-opt no-new-privileges --cap-drop ALL --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --memory 640m --cpus 1 --log-opt max-size=10m --log-opt max-file=3 \
  --env-file "$release_dir/release.env" -p 127.0.0.1:8000:8000 "$image" >/dev/null
ready=0
for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 3 http://127.0.0.1:8000/health \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and d.get("version")==sys.argv[1] else 1)' "$release_sha"; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" == 1 ]]
trap - ERR
echo "Backend image verified: $release_sha"
