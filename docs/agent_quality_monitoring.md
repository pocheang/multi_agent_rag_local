# Agent Quality Monitoring - API Documentation

## Overview

The Agent Quality Monitoring system provides comprehensive real-time monitoring and analytics for all agents in the multi-agent RAG system. It tracks execution metrics, success rates, performance timings, and error distributions.

## Architecture

### Components

1. **AgentExecutionTracker** (`app/services/agent_execution_tracker.py`)
   - Singleton service for tracking agent executions
   - Thread-safe execution tracing
   - Automatic cleanup of old traces (TTL: 1 hour)
   - Aggregated statistics calculation

2. **Admin API Routes** (`app/api/routes/admin_agent_quality.py`)
   - RESTful API endpoints for quality metrics
   - Admin-only access with authentication
   - Real-time data aggregation

3. **Frontend Dashboard** (`frontend/src/pages/admin/AdminAgentQualityDashboard.tsx`)
   - Real-time monitoring dashboard
   - Interactive charts and visualizations
   - Auto-refresh capability (30s interval)

## API Endpoints

### GET `/api/v1/admin/agent-quality/stats`

Get comprehensive agent quality statistics for the dashboard.

**Response:**
```json
{
  "summary": {
    "total_agents": 11,
    "total_executions": 1234,
    "overall_success_rate": 0.95,
    "avg_response_time": 2.34,
    "active_agents": 8
  },
  "agents": [
    {
      "agent_name": "EnhancedRouterAgent",
      "total_executions": 234,
      "success_count": 230,
      "failure_count": 4,
      "success_rate": 0.983,
      "avg_execution_time": 0.45,
      "avg_token_usage": 1234.5,
      "last_execution": "2026-07-02T10:30:00+00:00",
      "error_types": {
        "TimeoutError": 3,
        "ValueError": 1
      }
    }
  ],
  "timeline": [
    {
      "timestamp": "2026-07-02T10:00:00",
      "success": 45,
      "failure": 2
    }
  ],
  "error_distribution": {
    "TimeoutError": 12,
    "ValueError": 5,
    "ConnectionError": 3
  }
}
```

### GET `/api/v1/admin/agent-quality/agents/{agent_name}`

Get detailed statistics for a specific agent.

**Parameters:**
- `agent_name` (path): Name of the agent (e.g., "EnhancedRouterAgent")

**Response:** Single agent object with detailed metrics

### GET `/api/v1/admin/agent-quality/timeline`

Get execution timeline data.

**Query Parameters:**
- `hours` (optional, default: 24): Number of hours to include (1-168)

**Response:**
```json
{
  "timeline": [...],
  "summary": {
    "total_success": 1180,
    "total_failure": 54,
    "success_rate": 0.956
  }
}
```

### GET `/api/v1/admin/agent-quality/errors`

Get error distribution with top errors ranked by frequency.

**Response:**
```json
{
  "error_distribution": {
    "TimeoutError": 12,
    "ValueError": 5
  },
  "total_errors": 20,
  "top_errors": [
    {
      "type": "TimeoutError",
      "count": 12,
      "percentage": 60.0
    }
  ]
}
```

### POST `/api/v1/admin/agent-quality/clear`

Clear all agent execution statistics (admin only).

**⚠️ Warning:** This action is irreversible and removes all historical data.

**Response:**
```json
{
  "status": "success",
  "message": "All agent execution statistics have been cleared"
}
```

## Frontend Dashboard Features

### Key Performance Indicators (KPIs)

1. **Total Agents** - Number of unique agents registered
2. **Active Agents** - Agents with executions in last hour
3. **Total Executions** - Aggregate execution count
4. **Success Rate** - Overall success percentage
5. **Avg Response Time** - Mean execution time across all agents

### Visualizations

1. **Success/Failure Timeline** - Line chart showing execution outcomes over time
2. **Error Distribution** - Pie chart of error type frequencies
3. **Execution Count by Agent** - Horizontal bar chart
4. **Avg Execution Time by Agent** - Performance comparison

### Interactive Features

- **Agent Filter** - Filter dashboard by specific agent
- **Auto-refresh** - Toggle 30-second auto-refresh
- **Export** - Export data as CSV or JSON
- **Manual Refresh** - On-demand data reload

## Usage Examples

### Tracking Agent Execution

Agents are automatically tracked when decorated with `@track_agent_execution`:

```python
from app.services.agent_execution_tracker import track_agent_execution

@track_agent_execution("MyCustomAgent")
async def my_agent_function(query: str, execution_id: str):
    # Agent logic here
    return {"result": "success"}
```

### Manual Tracking

```python
from app.services.agent_execution_tracker import AgentExecutionTracker

tracker = AgentExecutionTracker.get_instance()

# Start execution
execution_id = tracker.start_execution("user query", user_id="user123")

# Record agent step
step_id = tracker.record_agent_step(
    execution_id=execution_id,
    agent_name="CustomAgent",
    input_data={"query": "test"}
)

# Complete step
tracker.complete_agent_step(
    execution_id=execution_id,
    step_id=step_id,
    output_data={"result": "success"},
    metadata={"tokens": 1000}
)

# Complete execution
tracker.complete_execution(execution_id)
```

### Querying Statistics

```python
# Get comprehensive quality stats
stats = tracker.get_quality_stats()

# Get basic execution stats (legacy)
stats = tracker.get_execution_stats()

# Get specific execution trace
trace = tracker.get_execution_trace(execution_id)
```

## Configuration

### Environment Variables

- `AGENT_TRACE_TTL_HOURS` (default: 1) - How long to keep execution traces
- `AGENT_TRACE_CLEANUP_INTERVAL` (default: 300s) - Cleanup task interval

### Performance Considerations

1. **Memory Usage**: Traces are kept in-memory with automatic cleanup
2. **Thread Safety**: All operations are thread-safe using RLock
3. **Scalability**: Designed for single-node deployment; use external monitoring for distributed systems
4. **Data Retention**: 1-hour TTL balances observability with memory constraints

## Testing

Run the test suite:

```bash
# All agent quality tests
pytest tests/test_admin_agent_quality_api.py -v

# Specific test
pytest tests/test_admin_agent_quality_api.py::test_get_agent_quality_stats_with_data -v
```

## Security

- All admin endpoints require authentication via `require_admin` dependency
- User-specific data isolation via `user_id` field in traces
- Admin actions (clear stats) are logged with warnings

## Troubleshooting

### No Data Showing in Dashboard

1. Check if agents are being tracked (look for `@track_agent_execution` decorator)
2. Verify `execution_id` is passed to agent functions
3. Check trace TTL hasn't expired (default: 1 hour)
4. Ensure backend is running and accessible

### High Memory Usage

1. Reduce `AGENT_TRACE_TTL_HOURS` to lower value
2. Increase `AGENT_TRACE_CLEANUP_INTERVAL` frequency
3. Consider implementing persistent storage for long-term analytics

### Missing Agent Steps

1. Ensure agent functions include `execution_id` parameter
2. Check for exceptions during agent execution (they should still be tracked)
3. Verify decorator is applied correctly

## Future Enhancements

- [ ] Persistent storage for historical data
- [ ] Advanced filtering (date ranges, status filters)
- [ ] Performance alerts and notifications
- [ ] Agent comparison mode
- [ ] Export to external monitoring systems (Prometheus, Grafana)
- [ ] Real-time WebSocket updates
- [ ] Per-user execution statistics
