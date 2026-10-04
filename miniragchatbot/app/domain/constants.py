"""Behaviour constants.

Every timeout here is the default of a parameter of the function or constructor that applies it,
so tests pass small values instead of patching these names (D-68).
"""

AUTH_TIMEOUT_SECONDS = 10.0
TOP_K = 4  # hit@3 15/15 on the probe set; k=8 would hand emp-001 most of its 12 chunks (D-28)
HR_DEPARTMENT = "hr"  # the brief's single cross-department exception
FIRST_TOKEN_TIMEOUT_SECONDS = 8.0
TURN_TIMEOUT_SECONDS = 30.0  # consumer-side bound over retrieval, both passes and the tool
TOOL_TIMEOUT_SECONDS = 2.0  # ceiling for the ~1.0 s parallel mocks
CHUNK_OVERSIZE_LIMIT = 150  # bge tokens: above every measured section (35-74), inside 512 (E01)
CHUNK_TOKENIZER_MODEL = "BAAI/bge-small-en-v1.5"
OCR_RENDER_DPI = 300  # 150 dpi dropped the minimum OCR confidence to 0.655 (E01)
PARAGRAPH_GAP_FACTOR = 2.0  # between in-paragraph gaps (0.7-1.4x) and paragraph gaps (2.9-3.9x)
JWT_LEEWAY_SECONDS = 10
MAX_MESSAGE_CHARS = 2000
POLICY_VIOLATION_CLOSE_CODE = 1008
ABNORMAL_CLOSURE_CODE = 1006  # what Starlette reports when a send finds the client gone
MAX_TOKEN_CHARS = 4096  # R-01: jwt.decode work grows per byte; mint_tokens' tokens are ~250
