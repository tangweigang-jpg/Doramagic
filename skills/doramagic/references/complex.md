---
title: "n8n: Develop workflows, custom nodes, and integrations for n8n automation platform"
name: n8n
description: Develop workflows, custom nodes, and integrations for n8n automation platform
tags:
  - sdd-workflow
  - shared-architecture
  - domain-specific
custom_fields:
  layer: null
  artifact_type: null
  architecture_approaches: [ai-agent-based, traditional-8layer]
  priority: shared
  development_status: active
  skill_category: domain-specific
  upstream_artifacts: []
  downstream_artifacts: []
---

# n8n Workflow Automation Skill

## Purpose

Provide specialized guidance for developing workflows, custom nodes, and integrations on the n8n automation platform. Enable AI assistants to design workflows, write custom code nodes, build TypeScript-based custom nodes, integrate external services, and implement AI agent patterns.

## When to Use This Skill

Invoke this skill when:

- Designing automation workflows combining multiple services
- Writing JavaScript/Python code within workflow nodes
- Building custom nodes in TypeScript
- Integrating APIs, databases, and cloud services
- Creating AI agent workflows with LangChain
- Troubleshooting workflow execution errors
- Planning self-hosted n8n deployments
- Converting manual processes to automated workflows

Do NOT use this skill for:

- Generic automation advice (use appropriate language/platform skill)
- Cloud platform-specific integrations (combine with cloud provider skill)
- Database design (use database-specialist skill)
- Frontend development (n8n has minimal UI customization)

## Core n8n Concepts

### Platform Architecture

**Runtime Environment:**
- Node.js-based execution engine
- TypeScript (90.7%) and Vue.js frontend
- pnpm monorepo structure
- Self-hosted or cloud deployment options

**Workflow Execution Models:**
1. **Manual trigger** - User-initiated execution
2. **Webhook trigger** - HTTP endpoint activation
3. **Schedule trigger** - Cron-based timing
4. **Event trigger** - External service events (database changes, file uploads)
5. **Error trigger** - Workflow failure handling

**Fair-code License:**
- Apache 2.0 with Commons Clause
- Free for self-hosting and unlimited executions
- Commercial restrictions for SaaS offerings

### Node Types and Categories

**Core Nodes** (Data manipulation):
- **Code** - Execute JavaScript/Python
- **Set** - Assign variable values
- **If** - Conditional branching
- **Switch** - Multi-branch routing
- **Merge** - Combine data streams
- **Split In Batches** - Process large datasets incrementally
- **Loop Over Items** - Iterate through data

**Trigger Nodes** (Workflow initiation):
- **Webhook** - HTTP endpoint
- **Schedule** - Time-based execution
- **Manual Trigger** - User activation
- **Error Trigger** - Catch workflow failures
- **Start** - Default entry point

**Action Nodes** (500+ integrations):
- API connectors (REST, GraphQL, SOAP)
- Database clients (PostgreSQL, MongoDB, MySQL, Redis)
- Cloud services (AWS, GCP, Azure, Cloudflare)
- Communication (Email, Slack, Discord, SMS)
- File operations (FTP, S3, Google Drive, Dropbox)
- Authentication (OAuth2, API keys, JWT)

**AI Nodes** (LangChain integration):
- **AI Agent** - Autonomous decision-making
- **AI Chain** - Sequential LLM operations
- **AI Transform** - Data manipulation with LLMs
- **Vector Store** - Embedding storage and retrieval
- **Document Loaders** - Text extraction from files

### Data Flow and Connections

**Connection Types:**
1. **Main connection** - Primary data flow (solid line)
2. **Error connection** - Failure routing (dashed red line)

**Data Structure:**
```javascript
// Input/output format for all nodes
[
  {
    json: { /* Your data object */ },
    binary: { /* Optional binary data (files, images) */ },
    pairedItem: { /* Reference to source item */ }
  }
]
```

**Data Access Patterns:**
- **Expression** - `{{ $json.field }}` (current node output)
- **Input reference** - `{{ $('NodeName').item.json.field }}` (specific node)
- **All items** - `{{ $input.all() }}` (entire dataset)
- **First item** - `{{ $input.first() }}` (single item)
- **Item index** - `{{ $itemIndex }}` (current iteration)

### Credentials and Authentication

**Credential Types:**
- **Predefined** - Pre-configured for popular services (OAuth2, API key)
- **Generic** - HTTP authentication (Basic, Digest, Header Auth)
- **Custom** - User-defined credential structures

**Security Practices:**
- Credentials stored encrypted in database
- Environment variable support for sensitive values
- Credential sharing across workflows (optional)
- Rotation: Manual update required

## Workflow Design Methodology

### Planning Phase

**Step 1: Define Requirements**
- Input sources (webhooks, schedules, databases)
- Data transformations needed
- Output destinations (APIs, files, databases)
- Error handling requirements
- Execution frequency and volume

**Step 2: Map Data Flow**
- Identify trigger events
- List transformation steps
- Specify validation rules
- Define branching logic
- Plan error recovery

**Step 3: Select Nodes**

Decision criteria:
- Use **native nodes** when available (optimized, maintained)
- Use **Code node** for custom logic <50 lines
- Build **custom node** for reusable complex logic >100 lines
- Use **HTTP Request node** for APIs without native nodes
- Use **Execute Command node** for system operations (security risk)

### Implementation Phase

**Workflow Structure Pattern:**

```
[Trigger] → [Validation] → [Branch (If/Switch)] → [Processing] → [Error Handler]
                                ↓                      ↓
                          [Path A nodes]        [Path B nodes]
                                ↓                      ↓
                          [Merge/Output]         [Output]
```

**Modular Design:**
- Extract reusable logic to sub-workflows
- Use Execute Workflow node for modularity
- Limit main workflow to 15-20 nodes (readability)
- Parameterize workflows with input variables

**Error Handling Strategy:**

1. **Error Trigger workflows** - Capture all failures
2. **Try/Catch pattern** - Error output connections on nodes
3. **Retry logic** - Configure per-node retry settings
4. **Validation nodes** - If/Switch for data checks
5. **Notification** - Alert on critical failures (Email, Slack)

### Testing Phase

**Local Testing:**
- Execute with sample data
- Verify each node output (inspect data panel)
- Test error paths with invalid data
- Check credential connections

**Production Validation:**
- Enable workflow, monitor executions
- Review execution history for failures
- Check resource usage (execution time, memory)
- Validate output data quality

## Code Execution in Workflows

### Code Node (JavaScript)

**Available APIs:**
- **Node.js built-ins** - `fs`, `path`, `crypto`, `https`
- **Lodash** - `_.groupBy()`, `_.sortBy()`, etc.
- **Luxon** - DateTime manipulation
- **n8n helpers** - `$input`, `$json`, `$binary`

**Basic Structure:**
```javascript
// Access input items
const items = $input.all();

// Process data
const processedItems = items.map(item => {
  const inputData = item.json;

  return {
    json: {
      // Output fields
      processed: inputData.field.toUpperCase(),
      timestamp: new Date().toISOString()
    }
  };
});

// Return transformed items
return processedItems;
```

**Data Transformation Patterns:**

*Filtering:*
```javascript
const items = $input.all();
return items.filter(item => item.json.status === 'active');
```

*Aggregation:*
```javascript
const items = $input.all();
const grouped = _.groupBy(items, item => item.json.category);

return [{
  json: {
    summary: Object.keys(grouped).map(category => ({
      category,
      count: grouped[category].length
    }))
  }
}];
```

*API calls (async):*
```javascript
const items = $input.all();
const results = [];

for (const item of items) {
  const response = await fetch(`https://api.example.com/data/${item.json.id}`);
  const data = await response.json();

  results.push({
    json: {
      original: item.json,
      enriched: data
    }
  });
}

return results;
```

**Error Handling in Code:**
```javascript
const items = $input.all();

return items.map(item => {
  try {
    // Risky operation
    const result = JSON.parse(item.json.data);
    return { json: { parsed: result } };
  } catch (error) {
    return {
      json: {
        error: error.message,
        original: item.json.data
      }
    };
  }
});
```

