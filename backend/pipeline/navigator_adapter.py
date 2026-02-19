# # backend/pipeline/navigator_adapter.py
# """
# Adapts Navigator output to Multi-Agent System input
# """
# from backend.core.ir_export import IRExporter
# from backend.models.code_component import CodeComponent

# class NavigatorAdapter:
#     def transform(self, ir_output, dag_output):
#         """Convert Navigator IR + DAG to CodeComponent list"""
#         components = []
#         for node in dag_output.topologically_sorted_nodes:
#             # Transform to CodeComponent
#             pass
#         return components