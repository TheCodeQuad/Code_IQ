# """
# Anthropic API Client
# """
# from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
# from backend.api.client import BaseAPIClient, APIRequest, APIResponse
# import time
# import logging

# logger = logging.getLogger(__name__)

# class AnthropicClient(BaseAPIClient):
#     """Anthropic Claude API client"""
    
#     def __init__(self, api_key: str, config: dict):
#         super().__init__(api_key, config)
#         self.client = Anthropic(api_key=api_key)
#         self.default_model = config['models']['default']
    
#     def generate(self, request: APIRequest) -> APIResponse:
#         """Generate response from Claude"""
#         start_time = time.time()
        
#         try:
#             response = self.client.messages.create(
#                 model=request.model or self.default_model,
#                 max_tokens=request.max_tokens,
#                 temperature=request.temperature,
#                 messages=[
#                     {"role": "user", "content": request.prompt}
#                 ]
#             )
            
#             latency = time.time() - start_time
            
#             api_response = APIResponse(
#                 content=response.content[0].text,
#                 model=response.model,
#                 usage={
#                     'input_tokens': response.usage.input_tokens,
#                     'output_tokens': response.usage.output_tokens,
#                     'total_tokens': response.usage.input_tokens + response.usage.output_tokens
#                 },
#                 metadata=request.metadata,
#                 latency=latency
#             )
            
#             self.track_usage(api_response)
#             return api_response
            
#         except Exception as e:
#             logger.error(f"Anthropic API error: {e}")
#             raise
    
#     def generate_stream(self, request: APIRequest):
#         """Generate streaming response from Claude"""
#         try:
#             with self.client.messages.stream(
#                 model=request.model or self.default_model,
#                 max_tokens=request.max_tokens,
#                 temperature=request.temperature,
#                 messages=[
#                     {"role": "user", "content": request.prompt}
#                 ]
#             ) as stream:
#                 for text in stream.text_stream:
#                     yield text
                    
#         except Exception as e:
#             logger.error(f"Anthropic streaming API error: {e}")
#             raise