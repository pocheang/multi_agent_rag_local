# Legacy `configs/` directory

Runtime profiles were consolidated into [`config/profiles/`](../config/profiles/). Do not add new configuration files here.

Use the canonical deployment entrypoints:

```bash
./deploy/scripts/deploy.sh development balanced
```

The directory is retained only as a discoverable migration marker for older checkouts that referenced `configs/runtime-profiles/`.
