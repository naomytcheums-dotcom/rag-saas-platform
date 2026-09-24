import {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class RagSaasApi implements ICredentialType {
	name = 'ragSaasApi';
	displayName = 'RAG SaaS API';
	documentationUrl = 'https://github.com/naomytcheums-dotcom/rag-saas-platform/blob/main/docs/integrations/N8N.md';
	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'https://your-instance.example.com',
			placeholder: 'https://your-instance.example.com',
			description: 'The URL of your RAG SaaS Platform instance',
		},
		{
			displayName: 'Connection ID',
			name: 'connectionId',
			type: 'string',
			default: '',
			description: 'The integration connection ID from your dashboard',
		},
		{
			displayName: 'Bearer Token',
			name: 'token',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			description: 'The bearer token shown once when the connection was created',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.token}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '=/integrations/{{$credentials.connectionId}}/inbound',
			method: 'POST',
			body: {
				title: 'n8n connection test',
				body: 'This is a real test from n8n',
			},
		},
	};
}
