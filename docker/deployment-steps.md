# Deployment Steps

## Fix allowlist permissions (required for /user add/remove)

Run these commands on the host where the container binds `./data/admins`:

```sh
sudo chown -R 1000:1000 ./data/admins
chmod -R u+rwX ./data/admins
```
