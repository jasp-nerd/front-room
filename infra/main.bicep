// Front Room on Azure Container Apps: one container for the room server and the web app it serves.
// EU only (westeurope by default), logs and traces in Log Analytics and Application Insights.
// The AI and data services come from ai-and-data.bicep; their keys are read here, at deploy time, straight
// into Container App secrets, so no key is ever a parameter, an output or a file.
//
//   az deployment group create -g vu-education-lab-rg -f infra/main.bicep \
//     -p image=<registry>.azurecr.io/front-room:<tag> registryServer=<registry>.azurecr.io \
//        registryUsername=<user> registryPassword=<password>

@description('EU region for every resource.')
@allowed(['westeurope', 'swedencentral', 'northeurope', 'francecentral', 'germanywestcentral'])
param location string = 'westeurope'

@description('Container image, e.g. vuonderwijswerkplaats.azurecr.io/front-room:v1')
param image string

param registryServer string
param registryUsername string

@secure()
param registryPassword string

@description('Model-backed agents on the Foundry deployments. Off: every role uses its rule-based fallback.')
param liveAgents bool = true

@description('Where match events come from: "eventhubs" (the live feed) or "file" (the packaged demo match).')
@allowed(['eventhubs', 'file'])
param ingest string = 'file'

@description('Names of the resources ai-and-data.bicep created.')
param foundryName string = 'vu-front-room-foundry'
param cosmosName string = 'vu-front-room-cosmos'
param eventsName string = 'vu-front-room-events'

param owner string = 'j.f.l.meijerink@student.vu.nl'

var name = 'vu-front-room'
var tags = { project: 'front-room', owner: owner, env: 'dev' }

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosName
}

resource events 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventsName
}

resource eventsAccess 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' existing = {
  parent: events
  name: 'RootManageSharedAccessKey'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${name}-logs'
  location: location
  tags: tags
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${name}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${name}-app'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto' }
      registries: [{ server: registryServer, username: registryUsername, passwordSecretRef: 'registry-password' }]
      secrets: [
        { name: 'registry-password', value: registryPassword }
        { name: 'insights-connection', value: insights.properties.ConnectionString }
        { name: 'foundry-key', value: foundry.listKeys().key1 }
        { name: 'cosmos-key', value: cosmos.listKeys().primaryMasterKey }
        { name: 'eventhub-connection', value: eventsAccess.listKeys().primaryConnectionString }
      ]
    }
    template: {
      containers: [
        {
          name: 'front-room'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'FRONTROOM_LIVE', value: liveAgents ? '1' : '0' }
            // The Director's A2A agent card advertises this address to remote personal agents.
            { name: 'FRONTROOM_PUBLIC_URL', value: 'https://${name}-app.${env.properties.defaultDomain}' }
            // The room asks Pip, the Room Director, over A2A at its public card, with the same rules in-process as the fallback.
            { name: 'FRONTROOM_DIRECTOR_URL', value: 'https://${name}-app.${env.properties.defaultDomain}' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'insights-connection' }
            // Microsoft Foundry: the agents' models, Content Safety and Speech.
            { name: 'FRONTROOM_FOUNDRY_ENDPOINT', value: foundry.properties.endpoint }
            { name: 'FRONTROOM_FOUNDRY_PROJECT', value: 'https://${foundryName}.services.ai.azure.com/api/projects/front-room' }
            { name: 'FRONTROOM_FOUNDRY_KEY', secretRef: 'foundry-key' }
            { name: 'FRONTROOM_MODEL', value: 'gpt-5.6-luna' }
            { name: 'FRONTROOM_MODEL_FAST', value: 'gpt-5.4-mini' }
            { name: 'FRONTROOM_SPEECH_REGION', value: foundry.location }
            // Azure Cosmos DB: rooms, the fairness ledger, the as-run log and workflow checkpoints.
            { name: 'FRONTROOM_COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'FRONTROOM_COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'FRONTROOM_COSMOS_DATABASE', value: 'frontroom' }
            // Azure Event Hubs: the live synthetic match feed.
            { name: 'FRONTROOM_INGEST', value: ingest }
            { name: 'FRONTROOM_EVENTHUB_CONNECTION', secretRef: 'eventhub-connection' }
            { name: 'FRONTROOM_EVENTHUB_NAME', value: 'match-events' }
            { name: 'FRONTROOM_EVENTHUB_CONSUMER_GROUP', value: 'room-server' }
          ]
          probes: [{ type: 'Liveness', httpGet: { path: '/health', port: 8000 }, periodSeconds: 30 }]
        }
      ]
      // One replica keeps every screen of a room on the same server's sockets; room state, decisions and
      // checkpoints live in Cosmos DB, so a restart resumes where it was. One warm replica for the demo.
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output principalId string = app.identity.principalId
