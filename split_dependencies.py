"""
Script to split dependencies.py into functional modules.
"""
import re
from pathlib import Path

# Read the original dependencies.py
deps_file = Path('app/api/dependencies.py')
content = deps_file.read_text(encoding='utf-8')

# Split into sections
lines = content.split('\n')

# Find all function definitions with their line numbers
functions = []
for i, line in enumerate(lines):
    if line.startswith('def _'):
        functions.append((i, line))

print(f"Found {len(functions)} helper functions")
print()

# Extract each function with its body
def extract_function(start_line):
    """Extract a complete function from start_line."""
    func_lines = []
    indent_level = None

    for i in range(start_line, len(lines)):
        line = lines[i]

        # Start of function
        if i == start_line:
            func_lines.append(line)
            continue

        # Empty lines or comments
        if not line.strip() or line.strip().startswith('#'):
            func_lines.append(line)
            continue

        # Determine indent level from first non-empty line after def
        if indent_level is None and line.strip():
            indent_level = len(line) - len(line.lstrip())

        # Check if we've reached the next function or end of indentation
        if line.startswith('def ') or (indent_level and len(line) - len(line.lstrip()) < indent_level and line.strip()):
            break

        func_lines.append(line)

    return '\n'.join(func_lines)

# Categorize functions
categories = {
    'query': [
        '_query_limiter_key', '_is_overload_mode', '_query_cache_key',
        '_run_with_query_runtime', '_user_api_settings_for_runtime',
        '_trace_id', '_call_with_supported_kwargs', '_maybe_sign_response',
        '_normalize_agent_class_hint', '_normalize_retrieval_strategy',
        '_resolve_effective_agent_class', '_effective_strategy_for_session',
        '_launch_shadow_run', '_query_model_fingerprint_for_user',
    ],
    'session': [
        '_history_store_for_user', '_require_valid_session_id',
        '_require_existing_session_for_query', '_latest_answer_for_same_question',
    ],
    'document': [
        '_is_source_allowed_for_user', '_is_source_manageable_for_user',
        '_list_visible_documents_for_user', '_allowed_sources_for_user',
        '_allowed_sources_for_visible_filenames', '_source_mtime_ns',
        '_visible_index_fingerprint_for_user', '_vector_context_from_citations',
        '_enforce_result_source_scope', '_source_scope_needs_resynthesis',
        '_resynthesize_after_source_scope', '_list_visible_pdf_names_for_user',
        '_visible_doc_chunks_by_filename_for_user', '_is_file_inventory_question',
        '_build_user_file_inventory_answer', '_guess_agent_class_for_upload',
        '_is_probably_valid_upload_signature',
    ],
    'memory': [
        '_memory_store_for_user', '_memory_signals_from_result',
        '_build_memory_context_for_session', '_promote_long_term_memory',
    ],
    'admin': [
        '_parse_audit_ts', '_filter_audit_rows', '_parse_request_ts',
        '_extract_grounding_support_from_detail', '_load_benchmark_queries',
        '_check_ollama_ready', '_check_chroma_ready', '_runtime_diagnostics_summary',
    ],
    'response': [
        '_mask_api_key', '_api_settings_view', '_admin_model_settings_view',
        '_request_meta', '_client_ip', '_audit', '_normalize_prompt_fields',
        '_sse_response',
    ],
    'auth': [
        '_require_permission', '_auth_cookie_name', '_auth_cookie_samesite',
        '_resolve_auth_token', '_set_auth_cookie', '_clear_auth_cookie',
        '_enforce_cookie_csrf', '_request_origin', '_origin_is_allowed',
        '_is_valid_admin_approval_token', '_is_valid_admin_approval_token_for_actor',
        '_require_user', '_require_user_and_token',
    ],
}

# Extract functions by category
extracted = {cat: [] for cat in categories}

for line_num, line in functions:
    func_name = re.match(r'def (_[a-z_]+)\(', line).group(1)
    func_body = extract_function(line_num)

    # Find which category this function belongs to
    found = False
    for cat, func_list in categories.items():
        if func_name in func_list:
            extracted[cat].append((func_name, func_body))
            found = True
            break

    if not found:
        print(f"Warning: {func_name} not categorized")

# Print statistics
print("Extraction complete:")
for cat, funcs in extracted.items():
    print(f"  {cat}: {len(funcs)} functions")
