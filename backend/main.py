import os
import json
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Asif Tech AI Agent API")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE_URL")   # e.g. asif208.myshopify.com
SHOPIFY_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN")
SHOPIFY_API  = "2024-01"

SYSTEM_PROMPT = """You are a smart AI store manager for Asif Tech — a Shopify store selling tech gadgets and accessories.
You have tools to search products, look up orders and customers, and pull sales analytics.
Always use tools to get real data. Present results clearly and suggest useful next steps. Be concise and action-oriented."""

TOOLS = [
    {
        "name": "search_products",
        "description": "Search or list products in the Shopify store by title or tag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search term"},
                "limit": {"type": "integer", "description": "Max results, default 10"}
            }
        }
    },
    {
        "name": "list_orders",
        "description": "List recent orders from the store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results, default 10"},
                "status": {"type": "string", "description": "any | open | closed | cancelled"}
            }
        }
    },
    {
        "name": "get_order",
        "description": "Get full details of a specific order by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Shopify order ID"}
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "list_customers",
        "description": "List or search customers in the store.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results, default 10"},
                "query": {"type": "string", "description": "Search by name or email"}
            }
        }
    },
    {
        "name": "get_analytics",
        "description": "Get sales analytics: total revenue, order count, average order value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to look back, default 30"}
            }
        }
    }
]

async def shopify(method: str, path: str, params: dict = None) -> dict:
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API}/{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.request(method, url, headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()

async def run_tool(name: str, inp: dict) -> str:
    try:
        if name == "search_products":
            params = {"limit": inp.get("limit", 10)}
            if inp.get("query"):
                params["title"] = inp["query"]
            data = await shopify("GET", "products.json", params)
            items = [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "status": p["status"],
                    "price": p["variants"][0]["price"] if p.get("variants") else "N/A",
                    "inventory": sum(v.get("inventory_quantity", 0) for v in p.get("variants", []))
                }
                for p in data.get("products", [])
            ]
            return json.dumps({"products": items, "total": len(items)})

        elif name == "list_orders":
            params = {"limit": inp.get("limit", 10), "status": inp.get("status", "any")}
            data = await shopify("GET", "orders.json", params)
            items = [
                {
                    "id": o["id"],
                    "name": o["name"],
                    "total": o["total_price"],
                    "currency": o["currency"],
                    "payment": o["financial_status"],
                    "fulfillment": o.get("fulfillment_status", "unfulfilled"),
                    "customer": o.get("customer", {}).get("email", "Guest"),
                    "created": o["created_at"][:10]
                }
                for o in data.get("orders", [])
            ]
            return json.dumps({"orders": items, "total": len(items)})

        elif name == "get_order":
            data = await shopify("GET", f"orders/{inp['order_id']}.json")
            o = data.get("order", {})
            return json.dumps({
                "id": o.get("id"),
                "name": o.get("name"),
                "total": o.get("total_price"),
                "items": [{"title": li["title"], "qty": li["quantity"], "price": li["price"]} for li in o.get("line_items", [])],
                "customer": o.get("customer", {}).get("email"),
                "shipping": o.get("shipping_address", {}).get("address1"),
                "status": o.get("financial_status")
            })

        elif name == "list_customers":
            params = {"limit": inp.get("limit", 10)}
            if inp.get("query"):
                params["query"] = inp["query"]
            data = await shopify("GET", "customers.json", params)
            items = [
                {
                    "name": f"{c['first_name']} {c['last_name']}".strip(),
                    "email": c["email"],
                    "orders": c["orders_count"],
                    "spent": c["total_spent"],
                    "created": c["created_at"][:10]
                }
                for c in data.get("customers", [])
            ]
            return json.dumps({"customers": items, "total": len(items)})

        elif name == "get_analytics":
            data = await shopify("GET", "orders.json", {"limit": 250, "status": "any"})
            orders = data.get("orders", [])
            revenue = sum(float(o["total_price"]) for o in orders)
            count   = len(orders)
            avg     = revenue / count if count else 0
            paid    = sum(1 for o in orders if o["financial_status"] == "paid")
            return json.dumps({
                "period":        f"Last {inp.get('days', 30)} days (up to 250 orders)",
                "total_revenue": f"£{revenue:,.2f}",
                "total_orders":  count,
                "paid_orders":   paid,
                "avg_order":     f"£{avg:,.2f}"
            })

        return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []

class ChatResponse(BaseModel):
    reply:      str
    tools_used: List[str] = []
    history:    List[Dict[str, Any]] = []

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = list(req.history)
    messages.append({"role": "user", "content": req.message})

    tools_used: List[str] = []

    for _ in range(6):   # max 6 agentic turns
        resp = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS
        )

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            messages.append({"role": "assistant", "content": text})
            return ChatResponse(reply=text or "Done.", tools_used=tools_used, history=messages)

        # Serialize assistant content for history
        serialized: List[Dict] = []
        results:    List[Dict] = []

        for b in resp.content:
            if b.type == "text":
                serialized.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                tools_used.append(b.name)
                serialized.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
                result = await run_tool(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": result})

        messages.append({"role": "assistant", "content": serialized})
        messages.append({"role": "user",      "content": results})

    return ChatResponse(reply="Analysis complete.", tools_used=tools_used, history=messages)

@app.get("/")
def health():
    return {"status": "ok", "agent": "Asif Tech Shopify AI Agent"}
