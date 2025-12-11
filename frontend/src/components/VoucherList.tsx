
import { Table, Tag, Space, Button, Popconfirm } from 'antd'
import { EyeOutlined, SyncOutlined, DeleteOutlined } from '@ant-design/icons'
// import { Voucher } from '../types' 

interface VoucherListProps {
    data: any[]
    isLoading: boolean
    onViewXml: (id: number) => void
    onSync: (ids: number[]) => void
    onMap: (voucher: any) => void
    onDelete: (id: number) => void
    selectedRows: number[]
    setSelectedRows: (keys: number[]) => void
}

export default function VoucherList({ data, isLoading, onViewXml, onSync, onMap, onDelete, selectedRows, setSelectedRows }: VoucherListProps) {

    const columns = [
        { title: 'Date', dataIndex: 'date', key: 'date' },
        { title: 'Type', dataIndex: 'voucher_type', key: 'type', render: (t: string) => <Tag>{t.replace('_', ' ').toUpperCase()}</Tag> },
        { title: 'Number', dataIndex: 'voucher_number', key: 'number' },
        { title: 'Party', dataIndex: 'party_ledger_name', key: 'party' },
        { title: 'Amount', dataIndex: 'amount', key: 'amount', render: (a: number) => `₹${a?.toLocaleString()}` },
        {
            title: 'Status', key: 'status', render: (_: any, r: any) => {
                if (r.verification_status === 'unverified') return <Tag color="warning">Unverified</Tag>
                if (r.verification_status === 'verified' && r.status === 'draft') return <Tag color="cyan">Verified (Draft)</Tag>
                return <Tag color={{ draft: 'default', approved: 'green', queued: 'blue', synced: 'purple', failed: 'red' }[r.status as string] || 'default'}>{r.status.toUpperCase()}</Tag>
            }
        },
        {
            title: 'Actions', key: 'actions', render: (_: any, r: any) => (
                <Space>
                    {(r.status === 'draft' || r.verification_status === 'unverified') && (
                        <Button size="small" type="primary" onClick={() => onMap(r)}>Map</Button>
                    )}
                    <Button size="small" icon={<EyeOutlined />} onClick={() => onViewXml(r.id)}>XML</Button>
                    {r.status === 'approved' && <Button size="small" icon={<SyncOutlined />} onClick={() => onSync([r.id])}>Sync</Button>}
                    <Popconfirm
                        title="Delete voucher?"
                        description="Are you sure you want to delete this voucher?"
                        onConfirm={() => onDelete(r.id)}
                        okText="Yes"
                        cancelText="No"
                    >
                        <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            )
        }
    ]

    return (
        <Table
            dataSource={data}
            columns={columns}
            loading={isLoading}
            rowKey="id"
            rowSelection={{ selectedRowKeys: selectedRows, onChange: (keys) => setSelectedRows(keys as number[]) }}
        />
    )
}
