# Tutorial 01: API Testing with HTTP Files

Explore the Azure Content Understanding REST API interactively using VS Code's REST Client extension — no code required.

## What You'll Learn

- How to call CU REST APIs directly
- Content extraction (OCR, layout, tables)
- Domain-specific analyzers (invoice, receipt, tax forms)
- Custom analyzer creation and field extraction
- Video analysis
- Analyzer management (list, copy, delete)

## Prerequisites

### 1. Azure Subscription and Resource

The easiest way to get started is to use **[Content Understanding Studio](https://aka.ms/cu-studio)** to set up your subscription and Azure Foundry resource:

- **[Quickstart: Content Understanding Studio](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/content-understanding-studio?tabs=portal)** - Follow this guide to:
  - Create an Azure subscription (if needed)
  - Create a Microsoft Foundry resource
  - Configure default model deployments (GPT-4.1, GPT-4.1-mini, and text-embedding models)

### 2. VS Code REST Client Extension

Install the **[REST Client Extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)** — it lets you send HTTP requests directly from `.http` files in VS Code.

### 3. Environment Configuration

Copy the `.env.sample` file to `.env` and update it with your Azure Foundry resource credentials:

```
API_KEY=your-subscription-key
ENDPOINT_URL=your-endpoint-url
```

## Getting Started

1. Complete the prerequisites above
2. Open `CU-API-Testing-Guide.http` in VS Code
3. Click "Send Request" above any HTTP request to execute it
4. Follow the **QUICK START** section in the file to:
   - Check your model deployments
   - Try content extraction
   - Test domain-specific analyzers

## What's Included

| File | Description |
|------|-------------|
| `CU-API-Testing-Guide.http` | Complete API testing guide with all sections |
| `CU-API-Testing-Preview2.http` | Preview API features |
| `custom-analyzer-with-replace.http` | Custom analyzer with field replacement |

## Next Steps

Once you're comfortable with the REST API, move on to:
- **[Tutorial 02: Invoice Extraction](../02-Invoice-Extraction/)** — Build a document analyzer using the agent-based workflow
- **[Tutorial 03: Video Analysis](../03-Video-Analysis/)** — Build a video analyzer with timestamps

## Documentation

- [Azure Content Understanding Overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [REST API Reference](https://learn.microsoft.com/en-us/rest/api/contentunderstanding/operation-groups)
- [Content Understanding Studio](https://aka.ms/cu-studio)
