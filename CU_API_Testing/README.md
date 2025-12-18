# Azure Content Understanding - API Testing Guide

This folder contain a HTTP test file for working with the Azure Content Understanding REST API.

## What is Azure Content Understanding?

Azure Content Understanding analyzes documents, text, images, audio, and video transforming them into structured, searchable data. It provides prebuilt analyzers for common scenarios (invoices, tax forms, IDs, etc.) and allows you to build custom analyzers tailored to your specific needs.

## Prerequisites

### 1. Azure Subscription and Resource Setup

The easiest way to get started is to use **[Content Understanding Studio](https://aka.ms/cu-studio)** to set up your subscription and Azure Foundry resource:

- **[Quickstart: Content Understanding Studio](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/content-understanding-studio?tabs=portal)** - Follow this guide to:
  - Create an Azure subscription (if needed)
  - Create a Microsoft Foundry resource
  - Configure default model deployments (GPT-4.1, GPT-4.1-mini, and text-embedding models)

### 2. VS Code REST Client Extension

To use the `.http` files in this folder, you need to install the REST Client extension for Visual Studio Code:

- **[REST Client Extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)** - Allows you to send HTTP requests directly from `.http` files in VS Code

### 3. Environment Configuration

Copy the `.env.sample` file to `.env` and update it with your Azure Foundry resource credentials:

```
API_KEY=your-subscription-key
ENDPOINT_URL=your-endpoint-url
```

**Note:** The `.env` file is ignored by git to protect your credentials.

## Getting Started

1. Complete the prerequisites above
2. Open `cu-API-Testing-Guide.http` in VS Code
3. Click "Send Request" above any HTTP request to execute it
4. Follow the "QUICK START" section in the file to:
   - Check your model deployments
   - Try content extraction
   - Test domain-specific analyzers

## What's Included

The `cu-API-Testing-Guide.http` file includes examples for:

- **Content Extraction** - Extract text, tables, figures, and layout (no LLM required)
- **Domain-Specific Analyzers** - Analyze invoices, tax forms, IDs, receipts, and more
- **RAG Analyzers** - Prepare content for Retrieval-Augmented Generation
- **Custom Analyzers** - Build and use custom field extraction analyzers
- **Video Analysis** - Analyze video content with custom fields
- **Analyzer Management** - List, copy, and delete analyzers

## Documentation

- [Azure Content Understanding Overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [REST API Reference](https://learn.microsoft.com/en-us/rest/api/contentunderstanding/operation-groups)
- [Content Understanding Studio](https://aka.ms/cu-studio)
- [Quickstart: Use REST API](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api)

## Support

For issues or questions, refer to the [Azure Content Understanding documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/) or file an issue in this repository.
