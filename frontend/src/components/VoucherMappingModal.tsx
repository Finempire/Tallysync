
import { Modal, Form, Select, Button, Checkbox, message, Typography } from 'antd'
import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { companiesApi, vouchersApi } from '../api/client'

const { Text } = Typography

interface VoucherMappingModalProps {
    open: boolean
    onCancel: () => void
    voucher: any
}

export default function VoucherMappingModal({ open, onCancel, voucher }: VoucherMappingModalProps) {
    const [form] = Form.useForm()
    const queryClient = useQueryClient()
    const [createRule, setCreateRule] = useState(true)

    const { data: ledgers } = useQuery({
        queryKey: ['ledgers', voucher?.company],
        queryFn: () => companiesApi.getLedgers(voucher.company),
        enabled: !!voucher?.company
    })

    // Mutation removed in favor of direct API call for simplicity in this artifact


    // We need an update method in vouchersApi. It seems missing in client.ts for generic update.
    // Let's assume we can use a custom call or add it. 
    // Wait, client.ts has 'create' but not 'update' for vouchers?
    // Step 206 show vouchersApi keys: list, create, get, approve... NO update.

    // I will implement a temporary fix here to use axios directly or add generic update to client.ts later.
    // Ideally I should update clien.ts. But I can't interrupt this flow easily. 
    // I'll add 'update' to vouchersApi in client.ts in next step. For now writing code assuming it exists.

    // Re-evaluating: I should add update to client.ts first? No, I can write this file, it will error on lint/compile, then I fix client.ts.

    const handleSave = async (values: any) => {
        try {
            // 1. Update Voucher with Party Ledger
            // We need a specific endpoint to update just the ledger or generic patch.
            // Using a hypothetical vouchersApi.update(id, data)
            // Check if createRule is true
            if (createRule) {
                await companiesApi.createMappingRule(voucher.company, {
                    pattern: voucher.party_name,
                    pattern_type: 'exact',
                    ledger: values.party_ledger,
                    transaction_type: 'both',
                    priority: 10
                })
            }

            await vouchersApi.update(voucher.id, { party_ledger: values.party_ledger, verification_status: 'verified' })

            message.success('Mapped successfully')
            queryClient.invalidateQueries({ queryKey: ['vouchers'] })
            onCancel()
        } catch (error) {
            message.error('Mapping failed')
        }
    }

    useEffect(() => {
        if (voucher) {
            form.setFieldsValue({
                party_name: voucher.party_name
            })
        }
    }, [voucher, form])

    return (
        <Modal title="Map Party Ledger" open={open} onCancel={onCancel} footer={null}>
            <div style={{ marginBottom: 16 }}>
                <Text type="secondary">Mapping Party Name:</Text> <Text strong>{voucher?.party_name}</Text>
            </div>
            <Form form={form} layout="vertical" onFinish={handleSave}>
                <Form.Item name="party_ledger" label="Select Ledger" rules={[{ required: true }]}>
                    <Select showSearch optionFilterProp="children" placeholder="Search ledger...">
                        {(ledgers?.data?.results || ledgers?.data || []).map((l: any) => (
                            <Select.Option key={l.id} value={l.id}>{l.name}</Select.Option>
                        ))}
                    </Select>
                </Form.Item>

                <Form.Item>
                    <Checkbox checked={createRule} onChange={e => setCreateRule(e.target.checked)}>
                        Save as Auto-mapping Rule for future
                    </Checkbox>
                </Form.Item>

                <Form.Item>
                    <Button type="primary" htmlType="submit" block>Save Mapping</Button>
                </Form.Item>
            </Form>
        </Modal>
    )
}
