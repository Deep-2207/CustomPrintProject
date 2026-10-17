"""Request bodies. Pydantic checks shape and size; validation.py checks the rules that need the product."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    label: str = Field(max_length=60)
    mesh: str = Field(max_length=80)
    style: str = Field(default="print", pattern=r"^(emboss|deboss|print)$")
    max_chars: int = Field(default=28, ge=1, le=500)
    allow_images: bool = True
    allow_stickers: bool = True
    max_lines: int = Field(default=1, ge=1, le=10)        # how many text lines the area accepts
    u0: float = Field(default=0.0, ge=0, le=1)
    u1: float = Field(default=1.0, ge=0, le=1)
    aspect: float = Field(default=0.0, ge=0, le=100)       # width/height of the whole UV surface of the mesh (0 = auto)
    y0: float = Field(default=0.0, ge=0, le=1)             # top of the printable rectangle
    y1: float = Field(default=1.0, ge=0, le=1)             # bottom of the printable rectangle
    guide: bool = False                                    # draw a dashed outline of the area on the preview
    print_w_mm: float = Field(default=0, ge=0, le=2000)    # real size of the printed area (0 = not set); used for print files
    print_h_mm: float = Field(default=0, ge=0, le=2000)


class ProductIn(BaseModel):
    """Legacy admin page (platform products)."""
    slug: str = Field(pattern=r"^[a-z0-9-]{2,60}$")
    name: str = Field(max_length=120)
    model: dict
    sizes: list[dict] = []
    colors: list[dict] = []
    imprint_colors: list[dict] = []
    fonts: list[str] = ["Arial"]
    zones: list[Zone]
    body_meshes: list[str] = []
    price: dict = {}
    defaults: dict = {}
    sample: str = ""
    placeholder: str = ""
    demos: list[dict] = []
    seed_version: int = 0


class SellerProductEdit(BaseModel):
    """What a seller may change on their own product (see validation.merge_seller_edit)."""
    name: str = Field(min_length=1, max_length=120)
    sizes: list[dict] = Field(default=[], max_length=12)
    colors: list[dict] = Field(max_length=16)
    imprint_colors: list[dict] = Field(default=[], max_length=10)
    fonts: list[str] = Field(max_length=10)
    zones: list[Zone] = Field(max_length=8)
    defaults: dict = {}
    sample: str = Field(default="", max_length=100)
    placeholder: str = Field(default="", max_length=100)
    price: dict = {}


class DesignIn(BaseModel):
    slug: str
    seller: str | None = None        # the seller's link name; omitted for the platform's own demo products
    size: str | None = None
    body_color: str = "#1d6fe8"
    imprint_color: str = ""
    layers: list[dict] = Field(max_length=60)
    preview_png: str | None = Field(default=None, max_length=4_500_000)   # data URL of the rendered 3D view
    ref: str | None = Field(default=None, max_length=80)                  # the seller's own order or cart reference


class LeadIn(BaseModel):
    business: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=r"^\+?[0-9 \-]{7,18}$")
    email: str = Field(default="", max_length=120, pattern=r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$")
    sells: str = Field(default="", max_length=300)
    website: str = Field(default="", max_length=200)
    city: str = Field(default="Ahmedabad", max_length=60)
    company_site: str = ""           # honeypot: real visitors never see or fill this field


class RegisterIn(BaseModel):
    business: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(max_length=200)
    slug: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9-]{3,40}$")


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class NewProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9-]{2,60}$")
    template: str | None = None      # slug of a platform product to copy
    model_id: int | None = None      # or an uploaded 3D model


class StatusIn(BaseModel):
    status: str = Field(pattern=r"^(pending|active|suspended)$")


class PublishIn(BaseModel):
    published: bool


class DomainsIn(BaseModel):
    domains: list[str] = Field(max_length=20)


class KeyIn(BaseModel):
    kind: str = Field(pattern=r"^(public|secret)$")


class PlanIn(BaseModel):
    plan: str = Field(pattern=r"^[a-z]{3,16}$")
    setup_fee: int = Field(default=0, ge=0, le=1_000_000)
    setup_fee_paid: bool = False


class PasswordIn(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)
