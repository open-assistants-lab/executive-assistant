# Dynamic Subagents - Lessons Learned

**Date:** 2025-02-16
**Status:** Failed Approach - Documented for Future Reference

---

## Executive Summary

We attempted to implement "truly dynamic" subagents that would automatically specialize based on the task. The implementation failed because we took a **template-based approach with hardcoded knowledge** rather than a truly dynamic, LLM-driven approach.

**Key Insight:** Dynamic subagents need THREE components to be truly specialized:
1. **Dynamic Prompt** - Custom-generated system prompt for the specific task
2. **Dynamic Skills/Knowledge** - Task-specific expertise injected into the prompt
3. **Dynamic Tools** - Specialized tools selected for the domain (NOT generic tools)

---

## What We Tried

### Approach 1: Template-Based Dynamic Subagents (FAILED)

**Implementation:**
- Pre-defined 13 built-in specializations (researcher, analyst, coder, writer, etc.)
- Keyword matching to detect specialization type
- Fixed prompts for each specialization type
- All subagents got the same generic tools

**Example Flow:**
```
User: "What are the heavy metal requirements for importing tea?"

System:
1. Keyword detection: "requirement" → matches "compliance_officer"
2. Uses fixed template: "You are a compliance and regulatory specialist..."
3. Subagent has generic tools: [web_search, web_scrape, memory_save, memory_search]
4. No specialized knowledge about food imports

Result: Generic compliance information, NOT specific to tea imports
```

**Why It Failed:**
- ❌ Not truly dynamic - just picking from 13 fixed templates
- ❌ Generic tools - every subagent gets the same tools
- ❌ No specialized knowledge - prompts are generic, not domain-specific
- ❌ Keyword matching is rigid - can't understand nuanced tasks

### Approach 2: Skill Injection with Hardcoded Database (FAILED)

**Implementation:**
- Created `skill_database.py` with domain-specific knowledge
- Attempted to inject skills into prompts based on task/context
- Hardcoded knowledge for domains like food_import_regulatory, financial_analysis, etc.

**Example Skill Database Entry:**
```python
"food_import_regulatory": {
    "fsanz_standard_1_4_1_limits": {
        "lead (pb)": "0.1 mg/kg (wet weight)",
        "cadmium (cd)": "0.1 mg/kg (wet weight)",
        "mercury (hg)": "0.05 mg/kg (wet weight)",
    },
    "import_permit_process": [
        "1. Check import conditions via BICON",
        "2. Determine if permit is required",
        "3. Apply for import permit",
    ],
}
```

**Why It Failed:**
- ❌ Hardcoded knowledge doesn't scale - can't pre-define every domain
- ❌ Matching logic is brittle - keyword-based matching fails on nuanced tasks
- ❌ Maintenance nightmare - need to manually update every domain's knowledge
- ❌ Still template-based - just choosing from pre-defined skill categories

**Specific Issue We Encountered:**
```python
# Task: "What are the heavy metal requirements for importing tea?"
# Context: "tea imports to Australia"
# Specialization: "compliance_officer"

# Expected: Match food_import_regulatory
# Actual: Matched legal_compliance (because "compliance" in specialization)
```

The scoring logic kept matching generic categories over specific ones because:
- "compliance_officer" (specialization) matched "legal_compliance" (10 points)
- "tea imports" (context) matched "food_import_regulatory" (7 points)
- Generic specialization match outweighed specific context match

---

## What TRUELY Dynamic Subagents Need

### Component 1: Dynamic Prompt (LLM-Generated)

**Wrong Approach (What We Did):**
```python
# Template-based: Pick from 13 fixed prompts
base_prompts = {
    "compliance_officer": "You are a compliance specialist...",
    "researcher": "You are a research assistant...",
    # ... 11 more fixed prompts
}
```

**Right Approach:**
```python
# LLM analyzes task and generates custom prompt
async def generate_dynamic_prompt(task: str, context: str) -> str:
    """Use LLM to analyze task and generate specialized prompt."""
    # LLM analyzes: "This is about food import regulatory compliance
    #               for tea products entering Australia"
    #
    # LLM generates: "You are a specialist in Australian food import
    #                 regulations with deep expertise in tea product
    #                 contaminant limits, specifically heavy metals.
    #                 You possess comprehensive knowledge of:
    #
    #                 - FSANZ Standard 1.4.1 (Contaminants)
    #                 - DAFF import requirements
    #                 - BICON permit system
    #                 ..."
    return custom_generated_prompt
```

**Why This Works:**
- ✅ No fixed templates - prompt is custom for each task
- ✅ LLM understands nuance - knows difference between "tea" and "general food"
- ✅ Scalable - works for ANY domain, not just pre-defined ones
- ✅ Context-aware - prompt reflects specific task requirements

### Component 2: Dynamic Skills/Knowledge (Retrieved, Not Hardcoded)

**Wrong Approach (What We Did):**
```python
# Hardcoded skill database
SKILL_DATABASE = {
    "food_import_regulatory": {
        "lead_limit": "0.1 mg/kg",
        "cadmium_limit": "0.1 mg/kg",
        # ... manually maintained
    }
}
```

**Right Approach:**
```python
# LLM retrieves/extracts knowledge dynamically
async def get_specialized_knowledge(task: str, context: str) -> str:
    """Use LLM to retrieve specialized knowledge for this task."""
    # Option 1: Search web for specific knowledge
    # "What are FSANZ heavy metal limits for tea?"
    # → Retrieve: "Lead: 0.1 mg/kg, Cadmium: 0.1 mg/kg, ..."

    # Option 2: Extract from conversation/memory
    # "User has asked about tea imports before"
    # → Recall: "User imports bubble tea ingredients, needs FSANZ compliance"

    # Option 3: Generate specialized context
    # → LLM generates: "For tea products specifically, key contaminants are:
    #                   - Lead (Pb): 0.1 mg/kg
    #                   - Cadmium (Cd): 0.1 mg/kg
    #                   - ..."

    return retrieved_knowledge
```

**Why This Works:**
- ✅ No hardcoded database - knowledge is retrieved/generated on-demand
- ✅ Always up-to-date - fetches current regulations, not outdated data
- ✅ Scales to any domain - doesn't need pre-defined categories
- ✅ Context-aware - retrieves knowledge specific to the user's situation

### Component 3: Dynamic Tools (Domain-Specific, Not Generic)

**Wrong Understanding (What We Initially Thought):**
```python
# We thought we needed to pre-select tools for subagents
def create_subagent(task, context):
    # Select tools based on domain
    if "compliance" in task:
        tools = ["web_search", "regulation_db", "permit_checker"]
    else:
        tools = ["web_search"]  # Generic

    return subagent_with_tools(tools)
```

**Right Understanding:**
```python
# The LLM dynamically selects tools during conversation
# We DON'T pre-select tools - the LLM chooses what to use

# User: "What are heavy metal requirements for importing tea?"
#
# LLM: "Let me search for FSANZ standards..."
# → Uses web_search tool
#
# LLM: "Let me also check the DAFF import requirements..."
# → Uses web_scrape tool to get specific DAFF page
#
# LLM: "Let me look up the specific tea product codes..."
# → Uses web_search again with more specific query
```

**Key Insight:**
- ✅ Tools should NOT be pre-selected by code
- ✅ The LLM intelligently chooses which tools to use based on the task
- ✅ All subagents can have access to the same tools
- ✅ Specialization comes from PROMPT, not from tool availability

**Why Tool Pre-Selection Is Wrong:**
1. **DeepAgents architecture:** The framework is designed for LLM-driven tool selection
2. **Flexibility:** LLM can adapt tool usage based on conversation flow
3. **Emergent behavior:** LLM might combine tools in unexpected ways
4. **Maintenance:** Don't need to manually map domains to tools

**Example:**
```
Task: "What are heavy metal requirements for importing tea?"

With pre-selected tools (WRONG):
- Subagent gets: [web_search, fsanz_lookup, daff_checker]
- LLM only knows about these 3 tools
- Can't adapt if it needs a different tool

With LLM-selected tools (RIGHT):
- Subagent gets: [web_search, web_scrape, web_crawl, web_map, memory_save, memory_search, get_current_time]
- LLM chooses which tools to use based on the task
- Can adapt: "Let me search (web_search), then scrape the specific page (web_scrape),
             then save this to memory (memory_save) for future reference"
```

---

## Key Lessons

### Lesson 1: "Dynamic" Means LLM-Generated, Not Template-Based

**Template-Based (Not Dynamic):**
- Keyword matching → Fixed prompts
- Pre-defined categories
- Rigid, doesn't adapt

**Truly Dynamic (LLM-Generated):**
- Task analysis → Custom prompts
- Unlimited specializations
- Adaptive, context-aware

**Takeaway:** If you're using templates/keywords, it's not dynamic. Use LLM to analyze and generate.

### Lesson 2: Specialization Comes From Prompt Content, Not Tool Selection

**Wrong Approach:**
- "I need to give this subagent specialized tools"
- Pre-select tools based on domain
- Restrict tool availability

**Right Approach:**
- "I need to give this subagent specialized knowledge in its prompt"
- All subagents have access to all tools
- LLM chooses which tools to use

**Takeaway:** The LLM is smart enough to select tools. Focus on making the PROMPT specialized.

### Lesson 3: Hardcoded Knowledge Doesn't Scale

**Wrong Approach:**
- Maintain skill database with manual entries
- Update by hand when regulations change
- Limited to pre-defined domains

**Right Approach:**
- Retrieve knowledge dynamically (web search, memory, etc.)
- Always up-to-date
- Works for any domain

**Takeaway:** Don't hardcode knowledge. Retrieve it dynamically or use RAG.

### Lesson 4: Context Is More Important Than Specialization Labels

**What We Got Wrong:**
```python
specialization = "compliance_officer"  # Generic label
# Matched: legal_compliance (because "compliance" in name)
# Should match: food_import_regulatory (because context is "tea imports")
```

**What We Should Do:**
```python
context = "tea imports to Australia"  # Specific context
# Analyze: What regulatory domain applies to this context?
# → food_import_regulatory
# → Australian-specific (FSANZ, DAFF)
# → Tea-specific (product codes, testing requirements)
```

**Takeaway:** Context matters more than generic specialization labels. Analyze the specific situation, not just the category.

### Lesson 5: Progressive Disclosure Saves Tokens

**Concept:** When retrieving knowledge for injection:
- Layer 1 (Compact): ID, type, title only (for search results)
- Layer 2 (Full): Complete narrative with details (for specific memory)

**Example:**
```python
# Compact (Layer 1) - ~50 tokens per memory
[
  {"id": "123", "type": "preference", "title": "Prefers async communication"},
  {"id": "124", "type": "preference", "title": "Works on Project X"},
]

# Full (Layer 2) - ~200 tokens per memory
[
  {
    "id": "123",
    "type": "preference",
    "title": "Prefers async communication",
    "narrative": "User prefers Slack over Zoom for most communications. Finds that async communication allows for better thoughtful responses and doesn't disrupt workflow.",
    "confidence": 0.9,
    "created_at": "2025-02-01"
  }
]
```

**Benefits:**
- Search results show 5 memories = ~250 tokens (not ~1000)
- User sees list of what's available
- Only fetch full memory when needed
- ~10x token savings

**Takeaway:** Use progressive disclosure for memory/knowledge retrieval to save tokens.

---

## Architecture for Truly Dynamic Subagents

### Recommended Implementation

```python
# 1. Analyze task and generate prompt (LLM-powered)
async def create_dynamic_subagent(task: str, context: str = "") -> Subagent:
    """Create a truly dynamic subagent with custom prompt and knowledge."""

    # Step 1: LLM analyzes the task
    analysis = await analyze_task(task, context)
    # → Output: {"domain": "food_import_regulatory",
    #            "subdomain": "tea_products",
    #            "region": "australia",
    #            "specific_focus": "heavy_metal_contaminant_limits"}

    # Step 2: LLM generates custom prompt
    system_prompt = await generate_specialized_prompt(analysis)
    # → Output: "You are a specialist in Australian food import regulations
    #             with deep expertise in tea product contaminant limits..."

    # Step 3: Retrieve specialized knowledge (RAG/web search)
    knowledge = await retrieve_specialized_knowledge(analysis)
    # → Output: {"fsanz_limits": {...},
    #             "import_process": [...],
    #             "contacts": {...}}

    # Step 4: Inject knowledge into prompt
    enhanced_prompt = inject_knowledge(system_prompt, knowledge)

    # Step 5: Create subagent with ALL tools available
    subagent = Subagent(
        name=generate_unique_name(task, context),
        system_prompt=enhanced_prompt,
        tools=get_all_tools(),  # NOT pre-selected - LLM will choose
    )

    return subagent
```

### Key Components

#### 1. Task Analysis (LLM-Powered)

```python
async def analyze_task(task: str, context: str) -> dict:
    """Use LLM to analyze task and identify specialization."""
    prompt = f"""
    Analyze this task and identify:
    1. Domain: What field/domain does this belong to?
    2. Sub-domain: What specific area?
    3. Region: Is this region-specific?
    4. Specific focus: What specific aspect?

    Task: {task}
    Context: {context or "Not specified"}
    """

    # LLM analyzes and returns structured analysis
    return await llm_with_structured_output(prompt)
```

#### 2. Dynamic Prompt Generation

```python
async def generate_specialized_prompt(analysis: dict) -> str:
    """Generate custom prompt based on task analysis."""
    prompt = f"""
    You are an expert in {analysis['domain']}.
    Your specialty is {analysis['sub_domain']}.
    You focus on {analysis['region']} if applicable.

    Generate a system prompt that:
    1. Establishes expertise in this specific domain
    2. Lists key frameworks/standards relevant to this domain
    3. Describes the specialist's responsibilities
    4. Emphasizes providing specific, actionable advice

    Output a 200-400 word system prompt.
    """

    return await llm.generate(prompt)
```

#### 3. Knowledge Retrieval (RAG)

```python
async def retrieve_specialized_knowledge(analysis: dict) -> dict:
    """Retrieve specialized knowledge for this task."""
    # Option 1: Web search for current information
    if requires_current_info(analysis):
        search_results = await web_search(f"{analysis['domain']} {analysis['specific_focus']}")

    # Option 2: Memory retrieval
    relevant_memories = await memory_search(
        query=f"{analysis['domain']} {analysis['context']}",
        max_results=5
    )

    # Option 3: Knowledge base lookup (if available)
    kb_results = await knowledge_base.search(analysis)

    return aggregate_knowledge(search_results, relevant_memories, kb_results)
```

#### 4. Knowledge Injection

```python
def inject_knowledge(prompt: str, knowledge: dict) -> str:
    """Inject retrieved knowledge into prompt."""
    knowledge_section = "\n\n**Your Specialized Knowledge:**\n\n"

    for key, value in knowledge.items():
        knowledge_section += f"**{key}:**\n"
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                knowledge_section += f"  {sub_key}: {sub_value}\n"
        elif isinstance(value, list):
            for item in value:
                knowledge_section += f"  {item}\n"
        else:
            knowledge_section += f"{value}\n"
        knowledge_section += "\n"

    return prompt + knowledge_section
```

---

## Comparison: Before vs After

### Before (Our Failed Implementation)

```
User: "What are the heavy metal requirements for importing tea?"

System:
1. Keyword matching: "requirement" → compliance_officer
2. Load fixed template: "You are a compliance specialist..."
3. Inject hardcoded skills (if matched correctly)
4. Subagent has generic tools: [web_search, memory_save]

Response:
"Let me search for compliance requirements..."
[Generic search results]
"Not specific to tea or Australia"
```

**Problems:**
- ❌ Template-based (not dynamic)
- ❌ Generic prompt (not specialized)
- ❌ Hardcoded knowledge (limited, outdated)
- ❌ Generic tools (all subagents same)
- ❌ Poor matching (wrong category selected)

### After (Recommended Implementation)

```
User: "What are the heavy metal requirements for importing tea?"

System:
1. LLM analyzes: Food import regulatory compliance, tea products, Australia
2. LLM generates prompt: "You are a specialist in Australian food import
                          regulations with deep expertise in tea product
                          contaminant limits..."
3. LLM retrieves knowledge:
   - FSANZ Standard 1.4.1 limits (current)
   - DAFF import process (current)
   - Tea product codes (specific)
4. Create subagent with enhanced prompt + all tools

Response:
"According to FSANZ Standard 1.4.1, clause 2.1.2, the heavy metal
 limits for tea products are:
 • Lead (Pb): 0.1 mg/kg
 • Cadmium (Cd): 0.1 mg/kg
 • Mercury (Hg): 0.05 mg/kg

 Import requires:
 1. BICON import permit
 2. Certificate of Analysis with heavy metal testing
 3. Testing by NATA-accredited laboratory

 Contact: DAFF Biosecurity 1800 900 444"
```

**Benefits:**
- ✅ Truly dynamic (LLM-generated prompt)
- ✅ Specialized prompt (specific to tea/Australia)
- ✅ Current knowledge (retrieved on-demand)
- ✅ All tools available (LLM selects intelligently)
- ✅ Specific, actionable response

---

## Technical Recommendations

### 1. Use LLM for Generation, Not Selection

**Don't:**
```python
# Select from pre-defined options
specializations = ["researcher", "analyst", "coder", "writer"]
matched = match_keywords(task, specializations)
prompt = templates[matched]
```

**Do:**
```python
# Generate custom prompt
prompt = await llm.generate(f"Create a specialized system prompt for: {task}")
```

### 2. Retrieve Knowledge Dynamically

**Don't:**
```python
# Hardcoded database
knowledge = SKILL_DATABASE["food_import_regulatory"]
```

**Do:**
```python
# Retrieve on-demand
knowledge = await search_web_and_memory(
    query=f"{domain} {specific_focus}",
    context=context
)
```

### 3. Give All Subagents Access to All Tools

**Don't:**
```python
# Pre-select tools
if "compliance" in task:
    tools = ["web_search", "regulation_db"]
```

**Do:**
```python
# Let LLM choose
tools = get_all_tools()  # All subagents get all tools
# LLM intelligently selects which tools to use
```

### 4. Prioritize Context Over Generic Labels

**Don't:**
```python
# Match specialization label
if "compliance_officer" in specialization:
    return get_generic_compliance_skills()
```

**Do:**
```python
# Analyze specific context
if "tea imports" in context:
    return await get_food_import_knowledge(product="tea")
```

### 5. Use Progressive Disclosure for Knowledge

**Don't:**
```python
# Fetch full memories immediately
memories = memory_store.fetch_all()  # Expensive!
```

**Do:**
```python
# Search first (compact), fetch later (full)
search_results = memory_store.search(query)  # Layer 1: Compact
specific_memory = memory_store.get(id)       # Layer 2: Full
```

---

## Future Implementation Path

### Phase 1: LLM-Powered Prompt Generation
- [ ] Remove keyword matching and templates
- [ ] Implement `analyze_task()` using LLM
- [ ] Implement `generate_specialized_prompt()` using LLM
- [ ] Test prompt quality for various domains

### Phase 2: Dynamic Knowledge Retrieval
- [ ] Implement web search integration for current info
- [ ] Implement memory retrieval for context
- [ ] Implement knowledge injection into prompts
- [ ] Test knowledge accuracy and relevance

### Phase 3: Tool Selection (Or Lack Thereof)
- [ ] Ensure all subagents have access to all tools
- [ ] Test that LLM selects appropriate tools
- [ ] Monitor tool usage patterns
- [ ] Verify no need for pre-selection

### Phase 4: Evaluation & Testing
- [ ] Create evaluation suite for subagent specialization
- [ ] Measure response quality (specificity, accuracy)
- [ ] Measure token efficiency
- [ ] A/B test vs template-based approach

---

## Conclusion

Our attempt to implement "dynamic subagents" failed because we took a **template-based approach with hardcoded knowledge**. We learned that truly dynamic subagents require:

1. **LLM-Generated Prompts** - Not templates
2. **Retrieved Knowledge** - Not hardcoded databases
3. **Full Tool Access** - Not pre-selected tools

The key insight is that **dynamism comes from LLM intelligence, not from code logic**. The LLM should analyze tasks, generate prompts, retrieve knowledge, and select tools - not the code.

**Remember:**
- ✅ Dynamic = LLM-generated, not template-based
- ✅ Specialization = Prompt content, not tool selection
- ✅ Knowledge = Retrieved dynamically, not hardcoded
- ✅ Context > Generic labels

---

## Files Created (Now Deleted)

The following files were created as part of this failed approach and have been removed:

### Implementation Files (Deleted)
- `src/agent/subagent_manager.py` - Subagent creation and caching
- `src/agent/skill_database.py` - Hardcoded skill database
- `src/agent/dynamic_prompt_generator.py` - LLM-based prompt generation
- `src/agent/dynamic_subagents.py` - Keyword-based specialization detection
- `src/agent/tool_selection.py` - Tool selection logic (wrong approach)

### Documentation Files (Deleted)
- `docs/DYNAMIC_SUBAGENTS.md` - Dynamic subagent documentation
- `docs/SUBAGENT_TYPES.md` - Subagent type definitions

### Example Files (Deleted)
- `examples/dynamic_tools_skills_demo.py` - Demonstration of dynamic tools/skills
- `examples/truly_dynamic_subagents.py` - Comparison of template vs dynamic

### Test Files (Deleted)
- `tests/unit/test_dynamic_subagents.py` - Unit tests for dynamic subagents

---

## References

### DeepAgents Architecture
- Tool selection is LLM-driven, not code-driven
- All agents have access to all tools
- Specialization comes from system prompt, not tool availability

### Progressive Disclosure
- Layer 1: Compact search results (ID, type, title)
- Layer 2: Full fetch (complete narrative)
- Token savings: ~10x for search results

### LLM-Powered Generation
- Use LLM to analyze tasks and generate prompts
- Use LLM to retrieve and synthesize knowledge
- Use LLM to select tools during conversation

---

**Last Updated:** 2025-02-16
**Status:** Documented lessons learned from failed implementation
**Next Steps:** Implement truly dynamic subagents using LLM-powered generation
