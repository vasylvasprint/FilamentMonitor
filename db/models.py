"""Python dataclass models mirroring the SQLite schema."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Store:
    id: Optional[int]
    name: str
    base_url: str
    category_url: str
    scraper: str = "custom"
    needs_js: bool = False
    is_active: bool = True
    is_custom: bool = False
    created_at: Optional[datetime] = None


@dataclass
class PriceSnapshot:
    id: Optional[int]
    store_id: int
    product_name: str
    brand: Optional[str] = None
    plastic_type: Optional[str] = None
    color: Optional[str] = None
    weight_g: Optional[int] = None
    hardness: Optional[str] = None
    price_uah: Optional[float] = None
    price_per_kg: Optional[float] = None
    price_per_g: Optional[float] = None
    product_url: Optional[str] = None
    in_stock: bool = True
    image_url: Optional[str] = None
    scraped_at: Optional[datetime] = None


@dataclass
class InventorySpool:
    id: Optional[int]
    plastic_type: str
    initial_weight_g: int
    current_weight_g: int
    purchase_price: float
    brand: Optional[str] = None
    store_name: Optional[str] = None
    color: Optional[str] = None
    hardness: Optional[str] = None
    empty_spool_weight_g: int = 200
    purchase_date: Optional[date] = None
    status: str = "active"
    notes: Optional[str] = None
    snapshot_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @property
    def remaining_pct(self) -> float:
        if self.initial_weight_g == 0:
            return 0.0
        return min(100.0, (self.current_weight_g / self.initial_weight_g) * 100)

    @property
    def cost_per_gram(self) -> float:
        if self.initial_weight_g == 0:
            return 0.0
        return self.purchase_price / self.initial_weight_g


@dataclass
class PrintJob:
    id: Optional[int]
    spool_id: int
    project_name: str
    filament_used_g: float
    cost_uah: Optional[float] = None
    is_failed: bool = False
    gcode_filename: Optional[str] = None
    notes: Optional[str] = None
    printed_at: Optional[datetime] = None


@dataclass
class CustomUrl:
    id: Optional[int]
    url: str
    label: Optional[str] = None
    added_at: Optional[datetime] = None
    last_scraped: Optional[datetime] = None
