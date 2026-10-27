// The AI and data services Front Room runs on. Deploy once per environment, before main.bicep:
//
//   az deployment group create -g vu-education-lab-rg -f infra/ai-and-data.bicep
//
// - Microsoft Foundry (an AI Services account with a project): gpt-5.6-luna for the agents that reason
//   (hypothesis, skeptic, writer), gpt-5.4-mini for the quick per-fan ones (profiler, scorer), and
//   gpt-5.4 as the evaluation judge, all
//   DataZoneStandard so prompts stay in the EU data zone. The same account serves Content Safety
//   (fans' free text) and Speech (described audio). The project's tracing reads the app's Application Insights.
// - Azure Cosmos DB (serverless): rooms, the fairness ledger, the as-run log and workflow checkpoints.
// - Azure Event Hubs: the live synthetic match feed the room server ingests.

@description('EU region for the Foundry account (model availability decides: swedencentral has the DataZone models).')
param aiLocation string = 'swedencentral'

@description('EU region for the data services, next to the Container App.')
param dataLocation string = 'westeurope'

param owner string = 'j.f.l.meijerink@student.vu.nl'

@description('Application Insights the Foundry project shows traces from (created by main.bicep).')
param insightsName string = 'vu-front-room-insights'

var name = 'vu-front-room'
var tags = { project: 'front-room', owner: owner, env: 'prod' }

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: '${name}-foundry'
  location: aiLocation
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${name}-foundry'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: 'front-room'
  location: aiLocation
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// One deployment at a time: the account accepts deployment changes sequentially.
resource reasoning 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: 'gpt-5.4'
  sku: { name: 'DataZoneStandard', capacity: 200 }
  properties: { model: { format: 'OpenAI', name: 'gpt-5.4', version: '2026-03-05' } }
}

resource luna 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: 'gpt-5.6-luna'
  sku: { name: 'DataZoneStandard', capacity: 200 }
  properties: { model: { format: 'OpenAI', name: 'gpt-5.6-luna', version: '2026-07-09' } }
  dependsOn: [fast]
}

resource fast 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: 'gpt-5.4-mini'
  sku: { name: 'DataZoneStandard', capacity: 200 }
  properties: { model: { format: 'OpenAI', name: 'gpt-5.4-mini', version: '2026-03-17' } }
  dependsOn: [reasoning]
}

resource insights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: insightsName
}

// Foundry's tracing view reads the agents' OpenTelemetry spans from this Application Insights.
resource tracing 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'front-room-insights'
  properties: {
    category: 'AppInsights'
    target: insights.id
    authType: 'ApiKey'
    isSharedToAll: false
    credentials: { key: insights.properties.ConnectionString }
    metadata: { ApiType: 'Azure', ResourceId: insights.id }
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: '${name}-cosmos'
  location: dataLocation
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: dataLocation, failoverPriority: 0, isZoneRedundant: false }]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmos
  name: 'frontroom'
  properties: { resource: { id: 'frontroom' } }
}

// Rooms, decisions and cues are read a room at a time; checkpoints a workflow run at a time.
var containers = [
  { name: 'rooms', key: '/room' }
  { name: 'ledger', key: '/room' }
  { name: 'asrun', key: '/room' }
  { name: 'checkpoints', key: '/workflow' }
]

resource collections 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = [
  for c in containers: {
    parent: database
    name: c.name
    properties: { resource: { id: c.name, partitionKey: { paths: [c.key], kind: 'Hash' } } }
  }
]

resource events 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${name}-events'
  location: dataLocation
  tags: tags
  sku: { name: 'Standard', tier: 'Standard', capacity: 1 }
}

resource matchEvents 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: events
  name: 'match-events'
  properties: { partitionCount: 2, retentionDescription: { cleanupPolicy: 'Delete', retentionTimeInHours: 24 } }
}

resource roomServer 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: matchEvents
  name: 'room-server'
}

output foundryEndpoint string = foundry.properties.endpoint
output projectEndpoint string = 'https://${name}-foundry.services.ai.azure.com/api/projects/${project.name}'
output cosmosEndpoint string = cosmos.properties.documentEndpoint
