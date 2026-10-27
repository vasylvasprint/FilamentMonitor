"""Database facade module (aliases db.queries and db.schema)."""
from typing import Optional, List, Dict, Any
import db.queries as queries
from db.queries import *
from db.schema import get_connection, init_db

# Explicit re-export with identical signature for backward and cross-module compatibility
def get_latest_prices(
    plastic_types: Optional[List[str]] = None,
    in_stock_only: bool = False,
    store_ids: Optional[List[int]] = None,
    selected_colors: Optional[List[str]] = None,
    color_search: Optional[str] = None,
    search_query: Optional[str] = None,
    hardness: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Return only the most recent snapshot per (store, product_url) combo with filters.
    
    Accepts both `color_search` (legacy/unified) and `search_query` as keyword arguments.
    """
    return queries.get_latest_prices(
        plastic_types=plastic_types,
        in_stock_only=in_stock_only,
        store_ids=store_ids,
        selected_colors=selected_colors,
        color_search=color_search,
        search_query=search_query,
        hardness=hardness,
        **kwargs,
    )
