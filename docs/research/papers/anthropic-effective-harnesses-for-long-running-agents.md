# Effective Harnesses for Long-Running Agents

**Source**: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
**Author**: Justin Young
**Contributors**: David Hershey, Prithvi Rajasakeran, Jeremy Hadfield, Naia Bouscal, Michael Tingley, Jesse Mu, Jake Eaton, Marius Buleandara, Maggie Vo, Pedram Navid, Nadine Yasser, Alex Notov
**Published**: 2025-11-26
**Quickstart Repo**: anthropics/claude-quickstarts → autonomous-coding

---

As AI agents tackle increasingly complex projects spanning hours or days, a critical challenge emerges: maintaining progress across multiple context windows where each new session starts without memory of prior work.

## The Core Problem

Anthropic researchers identified two failure patterns when Claude attempted to build production-quality applications:

1. **Over-ambition**: The agent attempted to complete everything at once, exhausting context mid-implementation and leaving features half-finished and undocumented.

2. **False completion**: After some features were built, subsequent agent instances would declare the project done prematurely.

The analogy: "engineers working in shifts where each new engineer arrives with no memory of what happened on the previous shift."

## The Two-Part Solution

The researchers developed an approach using two specialized agent configurations (same model, different prompts):

### Initializer Agent (First Session Only)

The first session establishes foundational infrastructure, including:

- An `init.sh` script for running the development server
- A `claude-progress.txt` file tracking completed work
- Initial git commits documenting setup
- A comprehensive `feature_list.json` — expanding high-level user request into 200+ specific, testable requirements

Feature list JSON structure:
```json
{
    "category": "functional",
    "description": "New chat button creates a fresh conversation",
    "steps": [
      "Navigate to main interface",
      "Click the 'New Chat' button",
      "Verify a new conversation is created",
      "Check that chat area shows welcome state",
      "Verify conversation appears in sidebar"
    ],
    "passes": false
}
```

JSON was chosen over Markdown because "the model was less likely to inappropriately modify or delete JSON entries."

### Coding Agent (Subsequent Sessions)

Subsequent sessions focus on incremental feature development while maintaining code quality suitable for merging to main branches — "the kind of code that would be appropriate for merging to a main branch."

Key constraints:
- Work on **single features** per session
- Make descriptive git commits after completing work
- Update progress files with change summaries
- Leave code in mergeable, well-documented states
- Use git to revert problematic changes
- **"It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."**

## Key Environment Management Strategies

### Comprehensive Feature Lists

Creating a JSON-formatted feature inventory (200+ items in their claude.ai clone example) provides clear scope. Each feature includes specific steps and a "passes" status field. The researchers strongly discourage agents from editing this file except to update completion status.

### Incremental Progress Tracking

Rather than attempting multiple features simultaneously, agents work on one feature per session, committing progress to git with descriptive messages. This enables reverting failed changes and recovering working states.

### Rigorous Testing

Claude improved significantly when explicitly prompted to use browser automation tools (Puppeteer MCP) for end-to-end testing rather than relying solely on unit tests or command-line validation. Claude performs best when given browser automation tools and explicit instructions to test as end users would.

Acknowledged limitation: Browser-native alert modals aren't visible through Puppeteer MCP, causing features depending on these modals to remain consistently buggy.

## Session Initialization Steps

Each coding session follows a consistent startup routine:

1. Run `pwd` to confirm working directory
2. Read git logs and progress files to understand recent work
3. Select the highest-priority incomplete feature from the feature list
4. Start the development server via `init.sh`
5. Execute basic functionality tests before implementing new features

Typical session flow:
```
[Assistant] I'll start by getting my bearings and understanding the current state of the project.
[Tool Use] <bash - pwd>
[Tool Use] <read - claude-progress.txt>
[Tool Use] <read - feature_list.json>
[Assistant] Let me check the git log to see recent work.
[Tool Use] <bash - git log --oneline -20>
[Assistant] Now let me check if there's an init.sh script to restart the servers.
<Starts the development server>
[Assistant] Excellent! Now let me navigate to the application and verify that some fundamental features are still working.
<Tests basic functionality>
[Assistant] Based on my verification testing, I can see that the fundamental functionality is working well. The core chat features, theme switching, conversation loading, and error handling are all functioning correctly. Now let me review the tests.json file more comprehensively to understand what needs to be implemented next.
<Starts work on a new feature>
```

## Common Failure Modes and Mitigation

| Problem | Initializer Response | Coding Agent Response |
|---------|----------------------|----------------------|
| Premature project completion ("one-shotting") | Create comprehensive feature list | Reference feature list; work on one feature at a time |
| Undocumented bugs and messy code | Initialize git repository and progress notes | Begin sessions by reading progress files and testing; end with git commits and updates |
| Features marked complete without testing | Establish feature list | Self-verify all features; only mark passing after thorough testing |
| Time spent figuring out how to run the application | Write `init.sh` script for development server | Read and execute `init.sh` at session start |

## Future Directions

The researchers acknowledge open questions:
- Whether specialized agents (testing, QA, code cleanup) could outperform a single general-purpose agent
- Whether these patterns generalize beyond web development to scientific research or financial modeling

The work demonstrates that treating AI agents like human engineers — providing clear context, structured progress tracking, and incremental task decomposition — significantly improves performance across extended development cycles.

---

## Key Insights Summary

1. **Git 是记忆基础设施** — commit message = 跨 session 的结构化记忆
2. **JSON > Markdown** — 用于特性追踪时，JSON 的结构性防止模型随意篡改
3. **验证先行** — 每个 session 先验证已有功能，再开始新工作
4. **测试是强制的** — 给 agent 浏览器自动化工具 + 明确指令"像终端用户一样测试"
5. **增量推进** — 每次只做一个特性，做完 commit，保持可合并状态
6. **双角色同模型** — 不是两个不同模型，是同一模型用不同 prompt 扮演不同角色

*Downloaded and annotated on 2026-03-11*
