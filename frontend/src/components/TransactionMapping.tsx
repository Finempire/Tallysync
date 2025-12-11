import { useState, useEffect } from 'react'
import { Modal, Table, Button, Select, Tag, Space, message, Typography } from 'antd'
import { FileTextOutlined, ThunderboltOutlined, CloudUploadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { bankStatementsApi, tallyApi } from '../api/client'

const { Text } = Typography

interface TransactionMappingProps {
    open: boolean
    onClose: () => void
    statement: any
    tallyCompany: string
}

export default function TransactionMapping({ open, onClose, statement, tallyCompany }: TransactionMappingProps) {
    const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
    const [mappingLedger, setMappingLedger] = useState<string | null>(null)

    const queryClient = useQueryClient()

    // Fetch transactions for the statement
    const { data: transactionsData, isLoading, refetch } = useQuery({
        queryKey: ['statement-transactions', statement?.id],
        queryFn: () => bankStatementsApi.getTransactions(statement.id),
        enabled: !!statement?.id && open
    })

    // Fetch ALL ledgers for the company
    const { data: tallyLedgers } = useQuery({
        queryKey: ['tally-ledgers-all', tallyCompany],
        queryFn: () => tallyApi.getLedgers(tallyCompany),
        enabled: !!tallyCompany && open
    })

    // Filter out synced/queued transactions as per request
    const transactions = (transactionsData?.data?.results || transactionsData?.data || [])
        .filter((t: any) => !['synced', 'queued'].includes(t.status))

    const ledgers = tallyLedgers?.data?.ledgers || []

    // Mutation to map transactions
    const mapMutation = useMutation({
        mutationFn: (data: any) => bankStatementsApi.mapTransactions(data),
        onSuccess: () => {
            message.success('Transactions mapped successfully')
            refetch()
            setSelectedRowKeys([])
            setMappingLedger(null)
            queryClient.invalidateQueries({ queryKey: ['bank-statements'] })
        },
        onError: (err: any) => message.error('Failed to map: ' + (err.response?.data?.error || err.message))
    })

    // Mutation to approve transactions
    const approveMutation = useMutation({
        mutationFn: (data: any) => bankStatementsApi.approveTransactions(data),
        onSuccess: () => {
            message.success('Transactions approved')
            refetch()
            setSelectedRowKeys([])
            queryClient.invalidateQueries({ queryKey: ['bank-statements'] })
        },
        onError: (err: any) => message.error('Failed to approve')
    })

    // Mutation to generate vouchers
    const generateVouchersMutation = useMutation({
        mutationFn: (data: any) => bankStatementsApi.generateVouchers(data),
        onSuccess: (data: any) => {
            message.success(data?.data?.message || 'Vouchers generated successfully')
            refetch()
            queryClient.invalidateQueries({ queryKey: ['bank-statements'] })
        },
        onError: (err: any) => message.error('Failed to generate vouchers: ' + (err.response?.data?.error || err.message))
    })

    // Mutation for Auto Map
    const autoMapMutation = useMutation({
        mutationFn: (data: any) => bankStatementsApi.autoMapTransactions(data),
        onSuccess: (data: any) => {
            message.success(data?.data?.message || 'Auto-mapping completed')
            refetch()
            queryClient.invalidateQueries({ queryKey: ['bank-statements'] })
        },
        onError: (err: any) => message.error('Auto-map failed: ' + (err.response?.data?.error || err.message))
    })

    // Mutation for Push to Tally
    const pushToTallyMutation = useMutation({
        mutationFn: (data: any) => bankStatementsApi.pushVouchers(data),
        onSuccess: (data: any) => {
            message.success(data?.data?.message || 'Vouchers queued for sync')
            refetch()
        },
        onError: (err: any) => message.error('Push failed: ' + (err.response?.data?.error || err.message))
    })

    const handleMap = () => {
        if (!mappingLedger) {
            message.warning('Please select a ledger to map to')
            return
        }
        mapMutation.mutate({
            transaction_ids: selectedRowKeys,
            ledger_name: mappingLedger
        })
    }

    const handleSingleMap = (record: any, ledgerName: string) => {
        mapMutation.mutate({
            transaction_ids: [record.id],
            ledger_name: ledgerName
        })
    }

    const columns = [
        {
            title: 'Date', dataIndex: 'date', key: 'date', width: 120,
            render: (dateStr: string) => {
                const date = new Date(dateStr)
                // DD-MM-YYYY format
                return `${String(date.getDate()).padStart(2, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${date.getFullYear()}`
            }
        },
        { title: 'Description', dataIndex: 'description', key: 'desc', ellipsis: true },
        {
            title: 'Type', key: 'type', width: 100,
            render: (_: any, r: any) => (
                <Tag color={r.debit ? 'orange' : 'blue'}>
                    {r.debit ? 'Payment' : 'Receipt'}
                </Tag>
            )
        },

        {
            title: 'Debit', key: 'debit', width: 120, align: 'right' as const,
            render: (_: any, r: any) => r.debit ? <Text type="danger">{r.debit}</Text> : ''
        },
        {
            title: 'Credit', key: 'credit', width: 120, align: 'right' as const,
            render: (_: any, r: any) => r.credit ? <Text type="success">{r.credit}</Text> : ''
        },
        {
            title: 'Map To Ledger', key: 'map', width: 300,
            render: (_: any, r: any) => (
                <Select
                    style={{ width: '100%' }}
                    showSearch
                    placeholder="Select Ledger"
                    optionFilterProp="children"
                    defaultValue={r.mapped_ledger_name || r.suggested_ledger_name}
                    onChange={(value) => handleSingleMap(r, value)}
                    status={r.status === 'manually_mapped' ? 'success' : ''}
                >
                    {ledgers.map((l: any) => <Select.Option key={l.name} value={l.name}>{l.name}</Select.Option>)}
                </Select>
            )
        },
        {
            title: 'Status', dataIndex: 'status', key: 'status', width: 120,
            render: (s: string) => <Tag color={s === 'approved' ? 'green' : s === 'voucher_created' ? 'purple' : s === 'manually_mapped' ? 'blue' : 'default'}>{s.replace('_', ' ')}</Tag>
        }
    ]

    const rowSelection = {
        selectedRowKeys,
        onChange: (keys: React.Key[]) => setSelectedRowKeys(keys)
    }

    return (
        <Modal
            title={`Map Transactions: ${statement?.original_filename}`}
            open={open}
            onCancel={onClose}
            width="95%"
            style={{ top: 20 }}
            styles={{
                content: {
                    backgroundColor: 'rgba(255, 255, 255, 0.70)',
                    backdropFilter: 'blur(12px)'
                }
            }}
            footer={null}
        >
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                    <Select
                        placeholder="Select Ledger to Map"
                        style={{ width: 300 }}
                        showSearch
                        optionFilterProp="children"
                        onChange={setMappingLedger}
                        value={mappingLedger}
                    >
                        {ledgers.map((l: any) => <Select.Option key={l.name} value={l.name}>{l.name}</Select.Option>)}
                    </Select>
                    <Button type="primary" onClick={handleMap} disabled={selectedRowKeys.length === 0 || !mappingLedger}>
                        Map Selected
                    </Button>
                    <Button
                        icon={<ThunderboltOutlined />}
                        onClick={() => autoMapMutation.mutate({ statement_id: statement.id })}
                        loading={autoMapMutation.isPending}
                    >
                        Auto Map
                    </Button>
                    <Button onClick={() => approveMutation.mutate({ transaction_ids: selectedRowKeys })} disabled={selectedRowKeys.length === 0}>
                        Approve Selected
                    </Button>
                </Space>

                <Space>

                    <Button
                        icon={<CloudUploadOutlined />}
                        onClick={() => pushToTallyMutation.mutate({
                            statement_id: statement.id,
                            transaction_ids: selectedRowKeys.length > 0 ? selectedRowKeys : undefined
                        })}
                        // Enable if any items are selected/available. Backend handles validity.
                        // We check if there's anything AT LEAST mapped (auto or manual) or better.
                        disabled={
                            selectedRowKeys.length > 0
                                ? false
                                : transactions.length === 0
                        }
                        loading={pushToTallyMutation.isPending}
                    >
                        {selectedRowKeys.length > 0 ? 'Send Selected to Tally' : 'Send All to Tally'}
                    </Button>
                </Space>
            </div>

            <Table
                dataSource={transactions}
                columns={columns}
                rowKey="id"
                size="small"
                rowSelection={rowSelection}
                pagination={false}
                loading={isLoading}
                scroll={{ y: 'calc(100vh - 250px)' }}
            />
        </Modal>
    )
}
