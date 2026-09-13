# Security Guidelines for Orei BK808 Integration

## DO
- ✅ Change your matrix device's default password BEFORE installation
- ✅ Use strong, unique passwords for your matrix
- ✅ Place AV equipment on isolated network/VLAN
- ✅ Keep credentials in Home Assistant's encrypted database
- ✅ Use HTTPS (default, no configuration needed)
- ✅ Enable firewall rules to restrict access to matrix IP
- ✅ Regular firmware updates for your matrix device

## DON'T
- ❌ Commit credentials to git repositories
- ❌ Share configuration files with real IPs/passwords
- ❌ Store passwords in plaintext configuration files
- ❌ Expose matrix to public internet
- ❌ Use default credentials (Admin:admin)
- ❌ Log credentials in console or debug output

## Credential Storage

The integration stores credentials in Home Assistant's encrypted `core.config_entries` database using HA's built-in encryption. This means:

- ✅ Credentials encrypted at rest
- ✅ Accessible only to HA running as your user
- ✅ Never sent to external servers
- ✅ Deleted when you remove the integration

## Environment Variables (Advanced)

For YAML users who want extra security:

```yaml
# .env file (add to .gitignore!)
OREI_HOST=192.168.1.100
OREI_USERNAME=myuser
OREI_PASSWORD=mypassword

# secrets.yml (also add to .gitignore!)
orei_host: !env_var OREI_HOST
orei_username: !env_var OREI_USERNAME
orei_password: !env_var OREI_PASSWORD
