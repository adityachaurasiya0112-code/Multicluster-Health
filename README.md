# Multicluster-Health

A comprehensive multi-cluster Kubernetes health monitoring system with a professional NOC-style web dashboard and powerful CLI tools. Monitor the health status of multiple Kubernetes clusters in real-time with automatic refresh and detailed cluster metrics.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
[![GitHub](https://img.shields.io/badge/GitHub-adityachaurasiya0112--code%2FMulticluster--Health-blue?logo=github)](https://github.com/adityachaurasiya0112-code/Multicluster-Health)

## Features

✨ **Web Dashboard**
- Professional dark-themed NOC-style interface
- Real-time cluster health status with auto-refresh
- Color-coded status indicators (Healthy, Degraded, Critical, Unreachable)
- Utilization bars and metrics visualization
- Responsive design for desktop and mobile

🖥️ **CLI Tool**
- Check cluster health from command line
- Markdown and JSON output formats
- Batch operations across multiple clusters
- Integration-friendly CLI commands

📊 **Health Monitoring**
- Node status tracking
- Pod health aggregation
- Resource utilization metrics
- Cluster connectivity verification
- Detailed health summaries

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Kubernetes clusters with kubeconfig access
- pip or pipenv for dependency management

### Installation

```bash
# Clone the repository
git clone https://github.com/adityachaurasiya0112-code/Multicluster-Health.git
cd Multicluster-Health

# Install dependencies
pip install -r requirements.txt

# Or use the project configuration
pip install -e .
```

### Configuration

Create a `config.yaml` file to specify your Kubernetes clusters:

```yaml
clusters:
  - name: cluster-1
    context: my-cluster-1
  - name: cluster-2
    context: my-cluster-2
```

### Running the Dashboard

```bash
# Start the Flask web dashboard
python app.py

# Open http://localhost:5001 in your browser
```

The dashboard will auto-refresh every 30 seconds and display the health status of all configured clusters.

### Using the CLI

```bash
# Check all cluster health
multicluster-health check --config config.yaml

# Get JSON output for integration
multicluster-health check --config config.yaml --json

# Get markdown formatted summary
multicluster-health check --config config.yaml --markdown
```

## Project Structure

```
.
├── app.py                    # Flask web dashboard application
├── config.yaml               # Kubernetes cluster configuration
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Project metadata and configuration
├── verify_dashboard.py       # Dashboard validation script
├── README.md                 # This file
└── multicluster_health/      # Main package
    ├── __init__.py           # Package exports
    ├── aggregator.py         # Multi-cluster health aggregation
    ├── cli.py                # Command-line interface
    ├── clusters.py           # Kubernetes cluster management
    └── health.py             # Individual cluster health checks
```

## Dependencies

- **PyYAML** (≥6.0) - YAML configuration parsing
- **click** (≥8.0) - CLI framework
- **flask** (≥3.0) - Web framework
- **kubernetes** (≥30.0) - Kubernetes Python client

## Development

### Install in Development Mode

```bash
pip install -e .
```

### Run Tests

```bash
python verify_dashboard.py
```

### Project Layout

The package is organized into focused modules:

- **aggregator.py** - Collects health data from all clusters
- **cli.py** - Command-line interface with rich output formatting
- **clusters.py** - Kubernetes client initialization and context management
- **health.py** - Per-cluster health calculation and metrics

## API Reference

### Python API

```python
from multicluster_health import get_all_clusters_health, load_cluster_configs

# Load cluster configuration
configs = load_cluster_configs("config.yaml")

# Get health status for all clusters
health_data = get_all_clusters_health("config.yaml")
print(health_data)
```

### CLI Commands

```bash
# Main command
multicluster-health check [OPTIONS]

# Options:
#   --config PATH      Path to config.yaml (default: config.yaml)
#   --json             Output as JSON
#   --markdown         Output as Markdown
#   --help             Show help message
```

## Environment

Ensure your kubeconfig is properly configured:

```bash
# Verify kubeconfig is accessible
kubectl config get-contexts

# Set specific context
kubectl config use-context <context-name>
```

## Troubleshooting

### Dashboard not loading
- Verify Flask is running: `python app.py`
- Check port 5001 is available
- Ensure kubeconfig is accessible to the application

### Cluster connection errors
- Verify cluster contexts in `config.yaml` match `kubectl config get-contexts`
- Check kubeconfig file permissions
- Ensure network connectivity to cluster endpoints

### Missing metrics
- Verify cluster has metrics-server installed
- Check node kubelet is responding
- Review cluster resource availability

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

**Aditya Chaurasiya**
- GitHub: [@adityachaurasiya0112-code](https://github.com/adityachaurasiya0112-code)
- Repository: [Multicluster-Health](https://github.com/adityachaurasiya0112-code/Multicluster-Health)

## Support

For issues, questions, or suggestions:
- Open an issue on [GitHub Issues](https://github.com/adityachaurasiya0112-code/Multicluster-Health/issues)
- Check existing documentation in this README

---

**Last Updated:** 2026-08-14