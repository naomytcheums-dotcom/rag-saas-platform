import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class RagSaas implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'RAG SaaS',
		name: 'ragSaas',
		icon: 'file:ragSaas.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["action"]}}',
		description: 'Send data to RAG SaaS Platform',
		defaults: {
			name: 'RAG SaaS',
		},
		inputs: ['main'],
		outputs: ['main'],
		credentials: [
			{
				name: 'ragSaasApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Action',
				name: 'action',
				type: 'options',
				options: [
					{ name: 'Ingest Document', value: 'ingest_document' },
					{ name: 'Log Only', value: 'log_only' },
					{ name: 'Create Agent', value: 'create_agent' },
					{ name: 'Create Conversation', value: 'create_conversation' },
					{ name: 'Send Notification', value: 'send_notification' },
					{ name: 'Trigger Workflow', value: 'trigger_workflow' },
				],
				default: 'ingest_document',
				description: 'The action to perform on RAG SaaS Platform',
			},
			{
				displayName: 'Payload (JSON)',
				name: 'payload',
				type: 'json',
				default: '{\n  "title": "Example",\n  "body": "Example content"\n}',
				description: 'The JSON payload to send',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const credentials = await this.getCredentials('ragSaasApi');
		const baseUrl = credentials.baseUrl as string;
		const connectionId = credentials.connectionId as string;

		for (let i = 0; i < items.length; i++) {
			const action = this.getNodeParameter('action', i) as string;
			const payload = this.getNodeParameter('payload', i) as object;

			const body = { ...payload, action };

			try {
				const response = await this.helpers.httpRequestWithAuthentication.call(this, 'ragSaasApi', {
					method: 'POST',
					url: `${baseUrl}/integrations/${connectionId}/inbound`,
					body,
					json: true,
				});

				returnData.push({
					json: response,
					pairedItem: { item: i },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message },
						pairedItem: { item: i },
					});
					continue;
				}
				throw new NodeOperationError(this.getNode(), error as Error, { itemIndex: i });
			}
		}

		return [returnData];
	}
}
