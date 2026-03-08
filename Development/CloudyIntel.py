# %%
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from operator import add
from typing import TypedDict, Annotated, List, Dict, Any, Optional, cast
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import add_messages, StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_chroma import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings
import logging
import time

load_dotenv(override=True)

# Set up logging with granular levels
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# %%
mini_llm = ChatOpenAI(model="gpt-4o-mini")
serper = GoogleSerperAPIWrapper()
tool_web_search = Tool(
    name="web_search",
    func=serper.run,
    description="Useful for when you need more information from the web about a query"
)
# FIXED: Bind both tools together so architects can use both web search and RAG
# Note: RAG tool will be defined in cell 7, but we'll rebind here after both tools are available


embeddings = OllamaEmbeddings(model="nomic-embed-text")
vector_store = Chroma(
    collection_name="AWSDocs",
    persist_directory="./chroma_db_AWSDocs",
    embedding_function=embeddings,
)


# %%
# FIXED: Use gpt-4o for structured outputs (better schema compliance)
reasoning_llm = ChatOpenAI(model="gpt-5")
# reasoning_llm = ChatOpenAI(model="gpt-4o")


# %%
class DomainTask(BaseModel):
    """Schema for individual domain tasks"""
    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    task_description: str = Field(description="Clear description of the task for this domain")
    requirements: List[str] = Field(description="Key requirements and constraints for this domain")
    deliverables: List[str] = Field(description="Expected deliverables for this domain")


# %%
class TaskDecomposition(BaseModel):
    """Schema for the complete task decomposition"""
    user_problem: str = Field(description="The original user problem")
    decomposed_tasks: List[DomainTask] = Field(description="List of domain-specific tasks")
    overall_architecture_goals: List[str] = Field(description="High-level architecture goals")
    constraints: List[str] = Field(description="Global constraints that apply to all domains")


# %%
# FIXED: Added deep merge for nested dictionaries to prevent data loss
def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with right taking precedence over left. Performs deep merge for nested dicts."""
    result = left.copy()
    for key, value in right.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Deep merge nested dictionaries
            result[key] = merge_dicts(result[key], value)
        else:
            # Overwrite with new value
            result[key] = value
    return result

def last_value(left: Any, right: Any) -> Any:
    """Keep the last value (right takes precedence)."""
    return right

def or_reducer(left: bool, right: bool) -> bool:
    """Logical OR reducer for booleans."""
    return left or right

def overwrite_bool(left: bool, right: bool) -> bool:
    """Overwrite boolean value (right takes precedence). Used for factual_errors_exist to allow reset."""
    return right

def replace_list(left: List[Any], right: List[Any]) -> List[Any]:
    """Replace list completely (right takes precedence). Used for resetting state on iteration."""
    return right if right is not None else left

def append_list(left: List[Any], right: List[Any]) -> List[Any]:
    """
    Append right list to left list. Used for accumulating feedback from parallel validators.
    FIXED: Empty right list does NOT reset - only architect_supervisor explicitly resets via replace_list.
    FIXED: Properly handles items with and without domain keys for deduplication.
    """
    # FIXED: Empty right list means no new items to add, return left unchanged
    if not right:
        return left
    if not left:
        return right
    # Combine lists, avoiding duplicates based on domain if present
    combined = left.copy()
    for item in right:
        # FIXED: Handle items with domain key for deduplication
        if isinstance(item, dict) and 'domain' in item:
            domain = item['domain']
            # Remove existing entry for this domain if present
            combined = [x for x in combined if not (isinstance(x, dict) and x.get('domain') == domain)]
            combined.append(item)
        else:
            # FIXED: For items without domain key, check for exact match to avoid duplicates
            # This prevents accumulation of identical non-domain items
            if item not in combined:
                combined.append(item)
    return combined

def validation_feedback_reducer(left: List[Any], right: List[Any]) -> List[Any]:
    """
    Custom reducer for validation_feedback that supports both accumulation and reset.
    - If right is exactly [] (empty list), it's a reset signal from architect_supervisor
    - Otherwise, append/merge items (for validators to accumulate feedback)
    FIXED: More robust reset detection - only reset if right is explicitly empty list and left has content
    """
    # Check if this is a reset signal (empty list from architect_supervisor)
    # Only reset if right is empty AND left has content (to avoid resetting on initial state)
    if right == [] and left != []:
        # This is a reset - return empty list
        return []
    # Otherwise, use append_list logic for accumulation
    return append_list(left, right)

class State(TypedDict):
    # FIXED: Limit message accumulation - only keep essential messages
    # Messages are stored per-node in node outputs, not globally to prevent exponential growth
    messages: Annotated[List, add_messages]
    user_problem: Annotated[str, last_value]
    iteration_count: Annotated[int, last_value]
    min_iterations: Annotated[int, last_value]
    max_iterations: Annotated[int, last_value]
    
    architecture_domain_tasks: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    architecture_components: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    proposed_architecture: Annotated[Dict[str, Any], merge_dicts]

    # FIXED: Use replace_list for validation_feedback to allow clean reset on iteration
    # Validators will append by providing their feedback in a list, which will replace and accumulate properly
    # The reducer handles reset when architect_supervisor sets it to [] and accumulation when validators add items
    validation_feedback: Annotated[List[Dict[str, Any]], validation_feedback_reducer]
    validation_summary: Annotated[Optional[str], last_value]
    audit_feedback: Annotated[List[Dict[str, Any]], add]

    # FIXED: Changed to overwrite_bool so factual_errors_exist can be reset to False on new iteration
    factual_errors_exist: Annotated[bool, overwrite_bool]
    # Note: design_flaws_exist removed from iteration_condition check since it's never set
    # Kept in state for potential future audit phase implementation
    design_flaws_exist: Annotated[bool, or_reducer]

    final_architecture: Annotated[Optional[Dict[str, Any]], last_value]
    architecture_summary: Annotated[Optional[str], last_value]


# %%
memory_saver = MemorySaver()


# %%
# FIXED: Moved RAG tool definition here (before it's used) to fix cell order dependency

# RAG search function for AWS documentation
def rag_search_function(query: str, k: int = 5) -> str:
    """
    Search the AWS documentation vector database for relevant information.
    
    Args:
        query: The search query
        k: Number of documents to retrieve (default: 5)
    
    Returns:
        Formatted string with relevant documentation snippets
    FIXED: Limit snippet length to prevent overwhelming validator LLM context.
    """
    try:
        similar_docs = vector_store.similarity_search(query, k=k)
        if not similar_docs:
            return "No relevant documentation found in the vector database."
        
        results = []
        max_snippet_length = 1000  # FIXED: Limit each snippet to 1000 chars
        for i, doc in enumerate(similar_docs, 1):
            content = doc.page_content.strip()
            # Truncate long snippets
            if len(content) > max_snippet_length:
                content = content[:max_snippet_length] + "... [truncated]"
            results.append(f"[Document {i}]:\n{content}\n")
        
        return "\n---\n".join(results)
    except Exception as e:
        logging.error(f"Error in RAG search: {str(e)}")
        return f"Error searching vector database: {str(e)}"

# Create RAG search tool
tool_RAG_search = Tool(
    name="RAG_search",
    func=rag_search_function,
    description="Search AWS documentation vector database for accurate, up-to-date information about AWS services, configurations, and best practices. Use this to validate architectural recommendations against official AWS documentation."
)

# FIXED: Bind both tools together so agents can use both web search and RAG
llm_with_all_tools = mini_llm.bind_tools([tool_web_search, tool_RAG_search])
# Keep separate bindings for backward compatibility if needed
llm_with_web_search_tools = mini_llm.bind_tools([tool_web_search])
llm_with_rag_tools = mini_llm.bind_tools([tool_RAG_search])


# %%
def format_component_recommendations(domain_name: str, task_info: Dict[str, Any], generated_text: Optional[str]) -> str:
    """Return architect output or a structured fallback when no text was produced."""
    if generated_text and generated_text.strip():
        return generated_text.strip()

    requirements = task_info.get("requirements", []) or []
    deliverables = task_info.get("deliverables", []) or []
    sections = [
        f"### {domain_name.capitalize()} Domain Recommendations",
        f"Task focus: {task_info.get('task_description', 'No task description provided.')}",
    ]

    if requirements:
        sections.append("Key requirements covered:")
        sections.extend(f"- {item}" for item in requirements)

    if deliverables:
        sections.append("Planned deliverables:")
        sections.extend(f"- {item}" for item in deliverables)

    sections.append("(Generated text unavailable; using structured fallback.)")
    return "\n".join(sections)


# FIXED: Added comprehensive error handling for tool calls with retry logic and timeout
def execute_tool_calls(
    messages: List, 
    llm_with_tools, 
    tools: Dict[str, Tool], 
    max_iterations: int = 3,
    timeout: Optional[float] = 60.0,
    retry_attempts: int = 2
) -> AIMessage:
    """
    Helper function to execute tool calls in a loop with error handling, retry logic, and timeout.
    
    Args:
        messages: List of messages for the LLM
        llm_with_tools: LLM instance with tools bound
        tools: Dictionary of tool name to Tool object
        max_iterations: Maximum number of tool call iterations
        timeout: Maximum time in seconds for tool execution (None for no timeout)
        retry_attempts: Number of retry attempts for failed LLM calls
    
    Returns:
        Final response from LLM after tool calls (always returns AIMessage)
    """
    tool_iterations = 0
    final_response = None
    start_time = time.time()
    failed_tools = []  # Track failed tools to inform LLM
    
    try:
        while tool_iterations < max_iterations:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Tool execution timeout after {timeout}s")
                break
            
            # Retry logic for LLM calls
            response = None
            last_error = None
            for attempt in range(retry_attempts + 1):
                try:
                    response = llm_with_tools.invoke(messages)
                    break
                except Exception as e:
                    last_error = e
                    if attempt < retry_attempts:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"LLM invocation failed (attempt {attempt + 1}/{retry_attempts + 1}), retrying in {wait_time}s: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"LLM invocation failed after {retry_attempts + 1} attempts: {str(e)}")
            
            if response is None:
                error_msg = f"Failed to get LLM response after {retry_attempts + 1} attempts"
                if last_error:
                    error_msg += f": {str(last_error)}"
                return AIMessage(content=f"Error: {error_msg}")
            
            # FIXED: Validate response is not empty
            if not response or not hasattr(response, "content"):
                logger.warning(f"Empty or invalid LLM response at iteration {tool_iterations}")
                break
            
            if hasattr(response, "tool_calls") and response.tool_calls:
                messages.append(response)
                tool_failures_in_this_iteration = []
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    if tool_name in tools:
                        try:
                            tool_start = time.time()
                            # FIXED: Unpack args dict as kwargs for tool invocation
                            tool_args = tool_call.get("args", {})
                            if not isinstance(tool_args, dict):
                                # Convert non-dict args to dict format (e.g., string query becomes {"query": str})
                                logger.warning(f"Tool {tool_name} received non-dict args: {tool_args}, converting to dict")
                                if tool_args:
                                    # If it's a string or other type, wrap it in a dict with a generic key
                                    tool_args = {"query": str(tool_args)} if isinstance(tool_args, (str, int, float)) else {"input": tool_args}
                                else:
                                    tool_args = {}
                            tool_result = tools[tool_name].invoke(tool_args)
                            tool_time = time.time() - tool_start
                            logger.debug(f"Tool {tool_name} executed successfully in {tool_time:.2f}s")
                            
                            messages.append(ToolMessage(
                                content=str(tool_result),
                                tool_call_id=tool_call["id"]
                            ))
                        except Exception as e:
                            error_msg = f"Error executing tool {tool_name}: {str(e)}"
                            logger.error(error_msg)
                            failed_tools.append(tool_name)
                            tool_failures_in_this_iteration.append(tool_name)
                            
                            messages.append(ToolMessage(
                                content=error_msg,
                                tool_call_id=tool_call["id"]
                            ))
                    else:
                        error_msg = f"Unknown tool: {tool_name}"
                        logger.warning(error_msg)
                        messages.append(ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call["id"]
                        ))
                
                # If critical tools failed, add context to messages
                if tool_failures_in_this_iteration:
                    logger.warning(f"Tools failed in iteration {tool_iterations}: {tool_failures_in_this_iteration}")
                    # Add a system message to inform LLM about tool failures
                    messages.append(SystemMessage(
                        content=f"Warning: The following tools failed: {', '.join(tool_failures_in_this_iteration)}. Please proceed with available information."
                    ))
                
                tool_iterations += 1
            else:
                final_response = response
                break
        
        if final_response is None:
            # FIXED: Always return a message object, never None
            if messages:
                # Use last response if available - prefer AIMessage over ToolMessage
                last_message = messages[-1]
                if isinstance(last_message, AIMessage):
                    final_response = last_message
                else:
                    # Last message is ToolMessage or other - create an AIMessage with error info
                    error_info = f"Tool execution incomplete after {tool_iterations} iterations."
                    if failed_tools:
                        error_info += f" Failed tools: {', '.join(set(failed_tools))}"
                    final_response = AIMessage(content=error_info)
            else:
                # No messages at all - return error message
                final_response = AIMessage(
                    content="Error: Tool execution failed - no valid responses received."
                )
        
        return final_response
    except Exception as e:
        logger.error(f"Critical error in execute_tool_calls: {str(e)}", exc_info=True)
        return AIMessage(content=f"Error: Tool execution failed: {str(e)}")


# %%
def create_initial_state(user_problem: str, min_iterations: int = 1, max_iterations: int = 3) -> State:
    """
    Create the initial state for the architecture generation process.
    
    Args:
        user_problem: The user's architecture problem statement
        min_iterations: Minimum number of refinement iterations (default: 1)
        max_iterations: Maximum number of refinement iterations (default: 3)
    """
    return {
        "messages": [HumanMessage(content=user_problem)],
        "user_problem": user_problem,
        "iteration_count": 0,
        "min_iterations": min_iterations,
        "max_iterations": max_iterations,
        "architecture_domain_tasks": {},
        "architecture_components": {},
        "proposed_architecture": {},
        "validation_feedback": [],
        "validation_summary": None,
        "audit_feedback": [],
        "factual_errors_exist": False,
        "design_flaws_exist": False,
        "final_architecture": None,
        "architecture_summary": None
    }


# %%
# FIXED: Reset state properly on iteration - clear validation_feedback, architecture_components, and reset factual_errors_exist
def architect_supervisor(state: State) -> State:
    """
    Orchestrates the architecture generation process using structured output for task decomposition.
    Incorporates validation feedback for iterative refinement.
    FIXED: Properly resets state at start of each iteration.
    """
    iteration = state["iteration_count"] + 1
    print(f"--- Architect Supervisor (Iteration {iteration}) ---")
    
    # FIXED: Get validation feedback from previous iteration (before reset)
    previous_validation_feedback = state.get("validation_feedback", [])
    previous_validation_summary = state.get("validation_summary")
    
    # Prepare feedback context for refinement
    feedback_context = ""
    if previous_validation_feedback:
        feedback_context = "\n\nPrevious Validation Feedback:\n"
        for feedback in previous_validation_feedback:
            domain = feedback.get("domain", "unknown")
            result = feedback.get("validation_result", "")
            feedback_context += f"\n{domain.upper()} Domain: {result[:200]}...\n"
    
    if previous_validation_summary:
        feedback_context += f"\n\nValidation Summary: {previous_validation_summary}\n"
    
    system_prompt = f"""
    You are an architect supervisor for AWS cloud architecture.
    Your role is to decompose the user's problem into structured domain-specific tasks and assign them to different architect domain agents.

    User Problem: {state["user_problem"]}
    Current Iteration: {iteration} of {state.get("max_iterations", 3)}
    
    {feedback_context}

    Decompose the problem into structured tasks for these domains:
    1. compute (EC2, Lambda, ECS, EKS, Auto Scaling, etc.)
    2. network (VPC, Subnets, ALB, CloudFront, Route 53, Security Groups, etc.)
    3. storage (S3, EBS, EFS, etc.)
    4. database (RDS, DynamoDB, ElastiCache, etc.)

    For each domain, provide a clear task description, key requirements, constraints and expected deliverables.
    Also provide overall architecture goals and global constraints.
    
    If this is a refinement iteration (iteration > 1), incorporate the validation feedback to address identified issues.
    Ensure your output matches the TaskDecomposition schema perfectly.
    """

    # FIXED: Added error handling for LLM calls with retry logic
    try:
        # Create LLM with structured output
        structured_llm = reasoning_llm.with_structured_output(TaskDecomposition)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Retry logic for LLM calls
        task_decomposition = None
        last_error = None
        for attempt in range(3):  # 3 retry attempts
            try:
                response = structured_llm.invoke(messages)
                task_decomposition = cast(TaskDecomposition, response)
                
                # FIXED: Validate response is not empty
                if not task_decomposition or not task_decomposition.decomposed_tasks:
                    raise ValueError("Empty task decomposition received from LLM")
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.warning(f"architect_supervisor LLM call failed (attempt {attempt + 1}/3), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise
        
        if task_decomposition is None:
            raise ValueError(f"Failed to get task decomposition after retries: {last_error}")
    except Exception as e:
        logger.error(f"Error in architect_supervisor LLM call: {str(e)}", exc_info=True)
        # Return fallback state with all required fields
        error_msg = f"Error in task decomposition: {str(e)}"
        logger.error(error_msg)
        return cast(State, {
            "messages": [AIMessage(content=error_msg)],
            "user_problem": state["user_problem"],
            "iteration_count": iteration,
            "min_iterations": state.get("min_iterations", 1),
            "max_iterations": state.get("max_iterations", 3),
            "architecture_domain_tasks": {},
            "architecture_components": {},
            "proposed_architecture": {},
            "validation_feedback": [],
            "validation_summary": None,
            "audit_feedback": [],
            "factual_errors_exist": True,  # Mark as error to trigger retry
            "design_flaws_exist": False,
            "final_architecture": None,
            "architecture_summary": None
        })

    # Prepare the state update for architecture_domain_tasks
    # FIXED: Replace instead of merge to avoid stale data
    domain_tasks_update = {
        "decomposition": task_decomposition.model_dump(),
        "overall_goals": task_decomposition.overall_architecture_goals,
        "constraints": task_decomposition.constraints
    }
    
    for task in task_decomposition.decomposed_tasks:
        domain_key = task.domain.lower()
        domain_tasks_update[domain_key] = {
            "task_description": task.task_description,
            "requirements": task.requirements,
            "deliverables": task.deliverables
        }

    # FIXED: Reset state properly on new iteration
    # Note: user_problem, max_iterations, final_architecture, architecture_summary are preserved via last_value reducer
    # audit_feedback uses 'add' reducer and accumulates across iterations (by design for audit history)
    # FIXED: Don't add messages to global state - they cause exponential growth and context pollution
    return cast(State, {
        # FIXED: Don't add messages here - they pollute the supervisor context
        # "messages": [AIMessage(content=f"Task decomposition complete (Iteration {iteration}). Assigning to domain architects.")],
        "architecture_domain_tasks": domain_tasks_update,
        "iteration_count": iteration,
        # FIXED: Reset these on new iteration using proper reducers
        "validation_feedback": [],  # validation_feedback_reducer detects empty list as reset signal and clears previous feedback
        "architecture_components": {},  # Clear previous components
        "proposed_architecture": {},  # Clear previous architecture
        "factual_errors_exist": False,  # Reset error flag (will be overwritten by overwrite_bool reducer)
        "validation_summary": None,  # Clear previous summary
        # Note: user_problem, max_iterations preserved automatically via last_value reducer
        # Note: audit_feedback accumulates via 'add' reducer (by design - preserves audit history)
        # Note: final_architecture, architecture_summary preserved until final generation
    })


# %%
# FIXED: Added error handling and validation
def domain_architect(state: State, domain: str, domain_services: str) -> State:
    """
    Generic domain architect function to reduce code duplication.
    FIXED: Added error handling, response validation, and task validation.
    """
    logger.info(f"--- {domain.capitalize()} architect ---")
    
    domain_task = state["architecture_domain_tasks"].get(domain, {})
    overall_goals = state["architecture_domain_tasks"].get("overall_goals", [])
    constraints = state["architecture_domain_tasks"].get("constraints", [])
    
    # FIXED: Validate that domain_task exists and is not empty
    if not domain_task or not domain_task.get("task_description"):
        error_msg = f"No task assignment found for {domain} domain. Cannot generate architecture recommendations."
        logger.warning(error_msg)
        return cast(State, {
            "messages": [AIMessage(content=error_msg, name=f"{domain}_architect")],
            "architecture_components": {
                domain: {
                    "recommendations": error_msg,
                    "agent": f"{domain}_architect",
                    "task_info": domain_task,
                    "error": "No task assignment"
                }
            }
        })
    
    # FIXED: Get validation feedback for this specific domain from previous iteration
    # Extract domain-specific feedback from validation_feedback
    validation_feedback = state.get("validation_feedback", [])
    domain_feedback = [
        fb for fb in validation_feedback 
        if isinstance(fb, dict) and fb.get("domain", "").lower() == domain.lower()
    ]
    
    validation_context = ""
    if domain_feedback:
        validation_context = "\n\nPrevious Validation Feedback for this Domain:\n"
        for fb in domain_feedback:
            result = fb.get("validation_result", "")
            has_errors = fb.get("has_errors", False)
            status = "HAS ERRORS" if has_errors else "PASSED"
            validation_context += f"\n[{status}]: {result[:300]}...\n"
    
    system_prompt = f"""
    You are an AWS {domain.capitalize()} Domain Architect.
    Design the {domain} infrastructure based on the task.

    Original Problem: {state["user_problem"]}
    Current Iteration: {state["iteration_count"]}

    Your Specific Task:
    - Description: {domain_task.get('task_description', f'Design {domain} infrastructure')}
    - Requirements: {domain_task.get('requirements', [])}
    - Expected Deliverables: {domain_task.get('deliverables', [])}

    Overall Architecture Goals: {overall_goals}
    Global Constraints: {constraints}
    {validation_context}

    Design {domain} components ({domain_services}).
    Use web search if you need specific, up-to-date information.
    Provide detailed configuration recommendations.
    Focus *only* on the {domain} domain.
    
    If this is a refinement iteration, address any issues identified in the validation feedback.
    """

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["user_problem"])]
    
    # FIXED: Added error handling with standardized error messages
    # FIXED: Use llm_with_all_tools so architects can use both web search and RAG
    try:
        # Execute tool calls using helper function
        final_response = execute_tool_calls(
            messages, 
            llm_with_all_tools, 
            {"web_search": tool_web_search, "RAG_search": tool_RAG_search},
            timeout=60.0
        )
        
        # FIXED: Validate response
        if not final_response:
            raise ValueError(f"[{domain}_architect] No response from LLM")
        
        content = getattr(final_response, "content", "")
        if not content or not content.strip():
            raise ValueError(f"[{domain}_architect] Empty response from LLM")
        
        recommendations = format_component_recommendations(domain, domain_task, content)
        logger.info(f"{domain.capitalize()} architect completed successfully")
    except Exception as e:
        error_msg = f"[{domain}_architect] Error generating recommendations: {str(e)}"
        logger.error(error_msg, exc_info=True)
        recommendations = format_component_recommendations(
            domain, 
            domain_task, 
            error_msg
        )

    # FIXED: Don't add messages to global state - they cause exponential growth
    # Messages are already handled in execute_tool_calls, don't duplicate here
    return cast(State, {
        # FIXED: Remove message addition to prevent context pollution
        # "messages": [AIMessage(content=recommendations, name=f"{domain}_architect")],
        "architecture_components": {
            domain: {
                "recommendations": recommendations,
                "agent": f"{domain}_architect",
                "task_info": domain_task
            }
        }
    })


def compute_architect(state: State) -> State:
    """AWS compute domain architect."""
    return domain_architect(state, "compute", "EC2, Lambda, ECS, EKS, Auto Scaling, etc.")


# %%
def network_architect(state: State) -> State:
    """AWS network domain architect."""
    return domain_architect(state, "network", "VPC, Subnets, ALB, CloudFront, Route 53, Security Groups, etc.")


# %%
def storage_architect(state: State) -> State:
    """AWS storage domain architect."""
    return domain_architect(state, "storage", "S3, EBS, EFS, Glacier, etc.")


# %%
def database_architect(state: State) -> State:
    """AWS database domain architect."""
    return domain_architect(state, "database", "RDS, DynamoDB, ElastiCache, etc.")


# %%
# FIXED: Added error handling and validation
def architect_synthesizer(state: State) -> State:
    """
    Synthesizes the architecture components provided by the architect agents into a coherent architecture.
    This node acts as the synchronization point for all parallel architects.
    LangGraph merges state updates from all parallel branches before executing this node.
    FIXED: Added error handling and validation.
    """
    logger.info("--- Architect synthesizer (synchronization point) ---")
    all_components = state.get("architecture_components", {})
    
    # FIXED: Derive required domains from architecture_domain_tasks instead of hardcoding
    domain_tasks = state.get("architecture_domain_tasks", {})
    # Extract domain keys (exclude special keys like "decomposition", "overall_goals", "constraints", "validation_tasks")
    special_keys = {"decomposition", "overall_goals", "constraints", "validation_tasks"}
    required_domains = [k for k in domain_tasks.keys() if k not in special_keys]
    # FIXED: Sort domains deterministically for consistent ordering
    required_domains = sorted(required_domains)
    
    # Fallback to default domains if domain_tasks is empty
    if not required_domains:
        required_domains = ["compute", "network", "storage", "database"]
        logger.warning("No domain tasks found, using default domains")
    
    completed_domains = list(all_components.keys())
    missing_domains = [d for d in required_domains if d not in completed_domains]
    
    if missing_domains:
        logger.warning(f"Missing domains in synthesizer: {missing_domains}")
        logger.info(f"Completed domains: {completed_domains}")
        # Continue with available domains if some are missing
    else:
        logger.info(f"All {len(completed_domains)} domains present. Synthesizing architecture.")
    
    component_summaries = []
    for domain, info in all_components.items():
        # Check if recommendations are empty
        recommendation = info.get('recommendations', 'No recommendations provided.')
        if not recommendation.strip():
            recommendation = "No recommendations provided for this domain."
            
        component_summaries.append(f"**{domain.capitalize()} Domain:**\n{recommendation}\n")
    
    system_prompt = f"""
    You are an AWS Principal Solutions Architect.
    You have received architecture designs from your domain specialist architects.
    Your job is to synthesize these components into a single, coherent, and final architecture proposal.

    Original Problem: {state['user_problem']}
    Overall Goals: {state["architecture_domain_tasks"].get("overall_goals", [])}
    Global Constraints: {state["architecture_domain_tasks"].get("constraints", [])}

    Component Designs from Domain Architects:
    {"---".join(component_summaries)}

    Synthesize all these pieces into a final, unified architecture.
    Ensure the components work together.
    Provide a high-level summary and then the detailed, integrated design.
    """
    
    # FIXED: Added error handling with retry logic
    try:
        messages = [SystemMessage(content=system_prompt)]
        
        # Retry logic for LLM calls
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = reasoning_llm.invoke(messages)
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.warning(f"architect_synthesizer LLM call failed (attempt {attempt + 1}/3), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise
        
        # FIXED: Validate response
        if not response or not hasattr(response, "content") or not response.content:
            raise ValueError("[architect_synthesizer] Empty response from LLM")
        
        architecture_summary = response.content
        logger.info("Architect synthesizer completed successfully")
    except Exception as e:
        error_msg = f"[architect_synthesizer] Error synthesizing architecture: {str(e)}"
        logger.error(error_msg, exc_info=True)
        architecture_summary = error_msg

    # FIXED: Don't add messages to global state - they cause exponential growth
    return cast(State, {
        # FIXED: Remove message addition to prevent context pollution
        # "messages": [AIMessage(content=architecture_summary, name="architect_synthesizer")],
        "proposed_architecture": {
            "architecture_summary": architecture_summary,
            "source_components": all_components
        }
    })


# %%
class ValidationTask(BaseModel):
    """Schema for individual domain validation tasks"""
    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    components_to_validate: List[str] = Field(description="List of AWS services/components to validate")
    validation_focus: str = Field(description="Specific aspects to validate (configuration, best practices, compatibility, etc)")

class ValidationDecomposition(BaseModel):
    """Schema for validation task decomposition"""
    validation_tasks: List[ValidationTask] = Field(description="List of domain-specific validation tasks")


# %%
# FIXED: Added error handling
def validator_supervisor(state: State) -> State:
    """
    Implements the validator supervisor that divides validation tasks across domains.
    Uses structured output to decompose validation work.
    FIXED: Added error handling.
    """
    print("--- Validator Supervisor ---")
    
    architecture_components = state.get("architecture_components", {})
    proposed_architecture = state.get("proposed_architecture", {})
    
    system_prompt = f"""
    You are a validator supervisor for AWS cloud architecture validation.
    Your role is to decompose the validation task into domain-specific validation assignments.

    Original Problem: {state['user_problem']}
    
    Architecture Components to Validate:
    {architecture_components}
    
    Proposed Architecture Summary:
    {proposed_architecture.get('architecture_summary', 'No summary available')}

    Analyze the architecture components and create validation tasks for these domains:
    1. compute (EC2, Lambda, ECS, EKS, Auto Scaling, etc.)
    2. network (VPC, Subnets, ALB, CloudFront, Route 53, Security Groups, etc.)
    3. storage (S3, EBS, EFS, Glacier, etc.)
    4. database (RDS, DynamoDB, ElastiCache, etc.)

    For each domain that has components in the architecture:
    - List the specific AWS services/components that need validation
    - Specify what aspects to validate (configuration correctness, best practices, service compatibility, etc.)
    
    Only create validation tasks for domains that actually have components in the architecture.
    Ensure your output matches the ValidationDecomposition schema perfectly.
    """

    # FIXED: Added error handling with retry logic
    try:
        # Create LLM with structured output
        structured_llm = reasoning_llm.with_structured_output(ValidationDecomposition)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Retry logic for LLM calls
        validation_decomposition = None
        last_error = None
        for attempt in range(3):
            try:
                response = structured_llm.invoke(messages)
                validation_decomposition = cast(ValidationDecomposition, response)
                
                # FIXED: Validate response
                if not validation_decomposition or not validation_decomposition.validation_tasks:
                    raise ValueError("[validator_supervisor] Empty validation decomposition received")
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.warning(f"validator_supervisor LLM call failed (attempt {attempt + 1}/3), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise
        
        if validation_decomposition is None:
            raise ValueError(f"[validator_supervisor] Failed to get validation decomposition after retries: {last_error}")
    except Exception as e:
        error_msg = f"[validator_supervisor] Error in validator_supervisor: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Return fallback validation tasks
        validation_decomposition = ValidationDecomposition(validation_tasks=[])

    # Prepare validation tasks for each domain
    validation_tasks_update = {}
    for task in validation_decomposition.validation_tasks:
        domain_key = task.domain.lower()
        validation_tasks_update[domain_key] = {
            "components_to_validate": task.components_to_validate,
            "validation_focus": task.validation_focus
        }

    # FIXED: Use proper nested merge instead of shallow merge to preserve existing domain tasks
    existing_tasks = state.get("architecture_domain_tasks", {})
    # Deep merge validation_tasks into existing structure
    merged_tasks = merge_dicts(existing_tasks, {"validation_tasks": validation_tasks_update})
    
    return cast(State, {
        # FIXED: Don't add messages to global state
        # "messages": [AIMessage(content=f"Validation tasks decomposed. Assigning to domain validators.")],
        "architecture_domain_tasks": merged_tasks
    })


# %%
# FIXED: Improved error detection using LLM-based approach instead of keyword matching
def detect_errors_llm(validation_result: str) -> bool:
    """
    Use LLM to determine if validation result indicates errors.
    More reliable than keyword matching.
    FIXED: Improved YES/NO detection to avoid false positives.
    FIXED: Smart truncation preserves context from both ends of validation result.
    """
    try:
        # FIXED: Use smart truncation - take first 700 and last 300 chars to preserve context
        # This ensures we see both the beginning (structure) and end (conclusions) of validation
        max_length = 1000
        if len(validation_result) > max_length:
            # Take first 70% and last 30% to see both beginning and end
            first_part = validation_result[:700]
            last_part = validation_result[-300:]
            truncated_result = f"{first_part}\n\n[... {len(validation_result) - max_length} characters omitted ...]\n\n{last_part}"
        else:
            truncated_result = validation_result
        
        error_detection_prompt = f"""
        Analyze this validation result and determine if it indicates any errors, issues, or problems that need to be fixed.
        
        Validation Result:
        {truncated_result}
        
        Respond with ONLY the word "YES" if there are errors/issues that need fixing, or ONLY the word "NO" if everything is valid.
        Do not include any other text in your response.
        """
        
        response = mini_llm.invoke([SystemMessage(content=error_detection_prompt)])
        content = getattr(response, "content", "")
        if isinstance(content, str):
            result_text = content.strip().upper()
        else:
            result_text = str(content).strip().upper()
        
        # FIXED: More precise YES/NO detection - check for exact word boundaries
        # Check if result starts with YES or NO (to avoid false positives like "There are NO errors")
        if result_text.startswith("YES"):
            return True
        elif result_text.startswith("NO"):
            return False
        else:
            # Fallback to keyword matching if LLM response is unclear
            # FIXED: Use weighted scoring - strong indicators count more
            strong_indicators = ["error", "incorrect", "invalid", "misconfiguration", "wrong", "needs fix"]
            weak_indicators = ["problem", "should be", "issue", "fix", "improve"]
            
            strong_count = sum(1 for keyword in strong_indicators if keyword in validation_result.lower())
            weak_count = sum(1 for keyword in weak_indicators if keyword in validation_result.lower())
            
            # At least 1 strong indicator OR at least 2 weak indicators
            return strong_count >= 1 or weak_count >= 2
    except Exception as e:
        logger.warning(f"Error in LLM-based error detection, falling back to keyword matching: {str(e)}")
        # Fallback to improved keyword matching with weighted scoring
        strong_indicators = ["error", "incorrect", "invalid", "misconfiguration", "wrong", "needs fix"]
        weak_indicators = ["problem", "should be", "issue", "fix", "improve"]
        
        strong_count = sum(1 for keyword in strong_indicators if keyword in validation_result.lower())
        weak_count = sum(1 for keyword in weak_indicators if keyword in validation_result.lower())
        
        # At least 1 strong indicator OR at least 2 weak indicators
        return strong_count >= 1 or weak_count >= 2


# FIXED: Added comprehensive error handling and improved error detection
def domain_validator(state: State, domain: str, validation_checks: str) -> State:
    """
    Generic domain validator function to reduce code duplication.
    FIXED: Added error handling and improved error detection.
    """
    logger.info(f"--- {domain.capitalize()} Validator ---")
    
    validation_tasks = state.get("architecture_domain_tasks", {}).get("validation_tasks", {})
    domain_validation = validation_tasks.get(domain, {})
    domain_components = state.get("architecture_components", {}).get(domain, {})
    
    if not domain_validation:
        # FIXED: Return proper state structure even when skipping
        # The validation_feedback_reducer will handle appending this to existing feedback
        new_feedback = {
            "domain": domain,
            "status": "skipped",
            "reason": "No validation tasks assigned",
            "validation_result": f"No validation tasks assigned for {domain} domain.",
            "components_validated": [],
            "has_errors": False
        }
        
        return cast(State, {
            # FIXED: Don't add messages to global state
            # "messages": [AIMessage(content=f"No validation tasks for {domain} domain.", name=f"{domain}_validator")],
            "validation_feedback": [new_feedback],  # Reducer will append to existing
            "factual_errors_exist": False  # No errors if skipped
        })
    
    components_to_validate = domain_validation.get("components_to_validate", [])
    validation_focus = domain_validation.get("validation_focus", "general validation")
    recommendations = domain_components.get("recommendations", "")
    
    system_prompt = f"""
    You are a {domain} domain validator for AWS cloud architecture.
    Your role is to validate {domain} architecture recommendations against official AWS documentation.

    Original Problem: {state['user_problem']}
    
    Components to Validate: {components_to_validate}
    Validation Focus: {validation_focus}
    
    Proposed {domain.capitalize()} Architecture:
    {recommendations}
    
    Use the RAG_search tool to retrieve relevant AWS documentation for each component.
    Validate:
    {validation_checks}
    
    Provide a structured validation report with:
    - Valid components (correctly configured)
    - Issues found (errors, misconfigurations, or improvements needed)
    - Recommendations for fixes or improvements
    - Confidence level in the validation
    """
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=f"Validate these {domain} components: {', '.join(components_to_validate)}")]
    
    # FIXED: Added error handling with standardized error messages
    try:
        # Execute tool calls using helper function
        final_response = execute_tool_calls(
            messages,
            llm_with_rag_tools,
            {"RAG_search": tool_RAG_search},
            timeout=60.0
        )
        
        # FIXED: Validate response
        if not final_response:
            raise ValueError(f"[{domain}_validator] No response from validator LLM")
        
        validation_result = getattr(final_response, "content", "Validation completed.")
        if not validation_result or not validation_result.strip():
            validation_result = f"[{domain}_validator] Validation completed but no detailed results provided."
    except Exception as e:
        error_msg = f"[{domain}_validator] Error during validation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        validation_result = error_msg
    
    # FIXED: Improved error detection
    has_errors = detect_errors_llm(validation_result)
    
    # FIXED: The validation_feedback_reducer will handle appending and deduplication
    new_feedback = {
        "domain": domain,
        "validation_result": validation_result,
        "components_validated": components_to_validate,
        "has_errors": has_errors
    }
    
    return cast(State, {
        # FIXED: Don't add messages to global state
        # "messages": [AIMessage(content=validation_result, name=f"{domain}_validator")],
        "validation_feedback": [new_feedback],  # Reducer will append and deduplicate by domain
        "factual_errors_exist": has_errors
    })


# %%
def compute_validator(state: State) -> State:
    """Validates compute domain architecture components against AWS documentation."""
    validation_checks = """1. Service names and configurations are correct
    2. Best practices are followed
    3. Service compatibility and integration
    4. Configuration parameters are valid
    5. Any factual errors or misconfigurations"""
    return domain_validator(state, "compute", validation_checks)


# %%
def network_validator(state: State) -> State:
    """Validates network domain architecture components against AWS documentation."""
    validation_checks = """1. VPC configuration (CIDR blocks, subnets, routing)
    2. Security group rules and network ACLs
    3. Load balancer configurations
    4. DNS and CDN setup
    5. Network connectivity and routing
    6. Any factual errors or misconfigurations"""
    return domain_validator(state, "network", validation_checks)


# %%
def storage_validator(state: State) -> State:
    """Validates storage domain architecture components against AWS documentation."""
    validation_checks = """1. S3 bucket configurations and policies
    2. EBS volume types and configurations
    3. EFS setup and performance modes
    4. Storage lifecycle policies
    5. Encryption and access controls
    6. Any factual errors or misconfigurations"""
    return domain_validator(state, "storage", validation_checks)


# %%
def database_validator(state: State) -> State:
    """Validates database domain architecture components against AWS documentation."""
    validation_checks = """1. Database engine selection and configuration
    2. Instance types and sizing
    3. Backup and recovery configurations
    4. High availability and replication setup
    5. Security and encryption settings
    6. Any factual errors or misconfigurations"""
    return domain_validator(state, "database", validation_checks)


# %%
# FIXED: Added error handling
def validation_synthesizer(state: State) -> State:
    """
    Synthesizes all validation feedback from domain validators into a comprehensive summary.
    This node acts as the synchronization point for all parallel validators.
    FIXED: Added error handling.
    """
    print("--- Validation Synthesizer (synchronization point) ---")
    
    all_validation_feedback = state.get("validation_feedback", [])
    
    if not all_validation_feedback:
        return cast(State, {
            "messages": [AIMessage(content="No validation feedback available.", name="validation_synthesizer")],
            "validation_summary": "No validation was performed."
        })
    
    # Prepare validation summary
    validation_summaries = []
    total_errors = 0
    
    for feedback in all_validation_feedback:
        domain = feedback.get("domain", "unknown")
        has_errors = feedback.get("has_errors", False)
        result = feedback.get("validation_result", "")
        
        if has_errors:
            total_errors += 1
        
        validation_summaries.append(f"**{domain.capitalize()} Domain:**\n{result[:300]}...\n")
    
    system_prompt = f"""
    You are a validation synthesizer for AWS cloud architecture.
    Your role is to synthesize validation feedback from all domain validators into a comprehensive summary.

    Original Problem: {state['user_problem']}
    Current Iteration: {state['iteration_count']}
    
    Validation Feedback from All Domains:
    {"---".join(validation_summaries)}
    
    Total Domains with Errors: {total_errors}
    Factual Errors Detected: {state.get('factual_errors_exist', False)}
    
    Synthesize all validation feedback into a clear, actionable summary that includes:
    1. Overall validation status
    2. Key issues found across all domains
    3. Priority of fixes needed
    4. Recommendations for the next iteration (if errors exist)
    5. Confidence in the architecture (if no errors)
    """
    
    # FIXED: Added error handling with retry logic
    try:
        messages = [SystemMessage(content=system_prompt)]
        
        # Retry logic for LLM calls
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = reasoning_llm.invoke(messages)
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.warning(f"validation_synthesizer LLM call failed (attempt {attempt + 1}/3), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise
        
        # FIXED: Validate response
        if not response or not hasattr(response, "content") or not response.content:
            raise ValueError("[validation_synthesizer] Empty response from validation synthesizer")
        
        validation_summary = response.content
        logger.info("Validation synthesizer completed successfully")
    except Exception as e:
        error_msg = f"[validation_synthesizer] Error synthesizing validation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        validation_summary = error_msg
    
    # FIXED: Don't add messages to global state
    return cast(State, {
        # FIXED: Remove message addition to prevent context pollution
        # "messages": [AIMessage(content=validation_summary, name="validation_synthesizer")],
        "validation_summary": validation_summary
    })


def iteration_condition(state: State) -> str:
    """
    Determines whether to iterate (refine architecture) or finish (generate final architecture).
    FIXED: Now properly checks reset error flags and minimum iterations.
    Note: iteration_count is incremented at the start of each iteration, so if max_iterations=3,
    iterations will be 1, 2, 3. When iteration_count reaches max_iterations, we've completed all iterations.
    """
    iteration = state.get("iteration_count", 0)
    min_iterations = state.get("min_iterations", 1)
    max_iterations = state.get("max_iterations", 3)
    # FIXED: Only check factual_errors_exist since design_flaws_exist is never set
    has_errors = state.get("factual_errors_exist", False)
    
    logger.info(f"--- Iteration Decision (Iteration {iteration}/{max_iterations}, min: {min_iterations}) ---")
    logger.info(f"Errors detected: {has_errors}")
    
    # Continue iterating if we haven't reached minimum iterations
    if iteration < min_iterations:
        logger.info(f"Decision: ITERATE - Minimum iterations ({min_iterations}) not yet reached")
        return "iterate"
    
    # Continue iterating if there are errors and we haven't reached max iterations
    if has_errors and iteration < max_iterations:
        logger.info("Decision: ITERATE - Refining architecture based on validation feedback")
        return "iterate"
    
    # Finish if we've reached max iterations
    if iteration >= max_iterations:
        logger.info(f"Decision: FINISH - Maximum iterations ({max_iterations}) reached")
        return "finish"
    
    # Finish if no errors and minimum iterations are met
    logger.info("Decision: FINISH - No errors detected, architecture is valid")
    return "finish"


# FIXED: Added error handling with retry logic
def final_architecture_generator(state: State) -> State:
    """
    Generates the final architecture document when validation passes or max iterations reached.
    FIXED: Added error handling and retry logic.
    """
    logger.info("--- Final Architecture Generator ---")
    
    proposed_architecture = state.get("proposed_architecture", {})
    architecture_components = state.get("architecture_components", {})
    validation_summary = state.get("validation_summary", "")
    
    system_prompt = f"""
    You are a Principal Solutions Architect finalizing an AWS cloud architecture.
    Your role is to create a comprehensive, production-ready architecture document.

    Original Problem: {state['user_problem']}
    Total Iterations: {state['iteration_count']}
    
    Final Proposed Architecture:
    {proposed_architecture.get('architecture_summary', 'No summary available')}
    
    Architecture Components:
    {architecture_components}
    
    Validation Summary:
    {validation_summary}
    
    Create a final, comprehensive architecture document that includes:
    1. Executive Summary
    2. Architecture Overview
    3. Detailed Component Specifications
    4. Integration Points
    5. Security Considerations
    6. Cost Optimization Recommendations
    7. Deployment Strategy
    8. Monitoring and Operations
    
    Ensure the document is production-ready and actionable.
    """
    
    # FIXED: Added error handling with retry logic
    try:
        messages = [SystemMessage(content=system_prompt)]
        
        # Retry logic for LLM calls
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = reasoning_llm.invoke(messages)
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait_time = 2 ** attempt
                    logger.warning(f"final_architecture_generator LLM call failed (attempt {attempt + 1}/3), retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                else:
                    raise
        
        # FIXED: Validate response
        if not response or not hasattr(response, "content") or not response.content:
            raise ValueError("[final_architecture_generator] Empty response from final architecture generator")
        
        final_architecture_doc = response.content
        logger.info("Final architecture generator completed successfully")
    except Exception as e:
        error_msg = f"[final_architecture_generator] Error generating final architecture: {str(e)}"
        logger.error(error_msg, exc_info=True)
        final_architecture_doc = error_msg
    
    # FIXED: Don't add messages to global state - final architecture is stored in state
    return cast(State, {
        # FIXED: Remove message addition to prevent context pollution
        # "messages": [AIMessage(content=final_architecture_doc, name="final_architecture_generator")],
        "final_architecture": {
            "document": final_architecture_doc,
            "components": architecture_components,
            "proposed_architecture": proposed_architecture,
            "validation_summary": validation_summary,
            "iterations": state['iteration_count']
        },
        "architecture_summary": final_architecture_doc
    })


# %%
graph_builder = StateGraph(State)

# Add all architect nodes
graph_builder.add_node("architect_supervisor", architect_supervisor)
graph_builder.add_node("compute_architect", compute_architect)
graph_builder.add_node("network_architect", network_architect)
graph_builder.add_node("storage_architect", storage_architect)
graph_builder.add_node("database_architect", database_architect)
graph_builder.add_node("architect_synthesizer", architect_synthesizer)

# Add validator nodes
graph_builder.add_node("validator_supervisor", validator_supervisor)
graph_builder.add_node("compute_validator", compute_validator)
graph_builder.add_node("network_validator", network_validator)
graph_builder.add_node("storage_validator", storage_validator)
graph_builder.add_node("database_validator", database_validator)

# ARCHITECTURE GENERATION FLOW
# PARALLEL EXECUTION: All architects run in parallel after supervisor
graph_builder.add_edge(START, "architect_supervisor")

# All architects start in parallel from supervisor
graph_builder.add_edge("architect_supervisor", "compute_architect")
graph_builder.add_edge("architect_supervisor", "network_architect")
graph_builder.add_edge("architect_supervisor", "storage_architect")
graph_builder.add_edge("architect_supervisor", "database_architect")

# All architects converge at synthesizer
graph_builder.add_edge("compute_architect", "architect_synthesizer")
graph_builder.add_edge("network_architect", "architect_synthesizer")
graph_builder.add_edge("storage_architect", "architect_synthesizer")
graph_builder.add_edge("database_architect", "architect_synthesizer")

# VALIDATION FLOW (after architecture synthesis)
# After synthesizer, move to validation
graph_builder.add_edge("architect_synthesizer", "validator_supervisor")

# Validators run in parallel after validator supervisor
graph_builder.add_edge("validator_supervisor", "compute_validator")
graph_builder.add_edge("validator_supervisor", "network_validator")
graph_builder.add_edge("validator_supervisor", "storage_validator")
graph_builder.add_edge("validator_supervisor", "database_validator")

# Add new nodes for iteration loop
graph_builder.add_node("validation_synthesizer", validation_synthesizer)
graph_builder.add_node("final_architecture_generator", final_architecture_generator)

# All validators converge at validation synthesizer
graph_builder.add_edge("compute_validator", "validation_synthesizer")
graph_builder.add_edge("network_validator", "validation_synthesizer")
graph_builder.add_edge("storage_validator", "validation_synthesizer")
graph_builder.add_edge("database_validator", "validation_synthesizer")

# ITERATION LOOP: After validation synthesizer, decide whether to iterate or finish
graph_builder.add_conditional_edges(
    "validation_synthesizer",
    iteration_condition,
    {
        "iterate": "architect_supervisor",  # Loop back to refine architecture
        "finish": "final_architecture_generator"  # Generate final architecture
    }
)

# Final architecture generator leads to END
graph_builder.add_edge("final_architecture_generator", END)


# %%
# FIXED: Added memory_saver for checkpointing
graph = graph_builder.compile(checkpointer=memory_saver)
graph


# %%
# FIXED: Test the graph with proper checkpointer configuration
# When using MemorySaver, you must provide a config with thread_id
config = {"configurable": {"thread_id": "test-run-4"}}

result = graph.invoke(
    create_initial_state("Guidance for Building a Containerized and Scalable Web Application on AWS", min_iterations=2, max_iterations=3), 
    config=config  # type: ignore
)
result


# %%