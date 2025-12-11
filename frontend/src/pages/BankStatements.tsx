import { useState, useEffect } from 'react'
import { Card, Table, Button, Upload, Modal, Form, Select, message, Tag, Space, Typography, Progress, Alert, Spin, Popconfirm } from 'antd'
import { UploadOutlined, EyeOutlined, CheckOutlined, DownloadOutlined, SyncOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { bankStatementsApi, tallyApi } from '../api/client'
import TransactionMapping from '../components/TransactionMapping'

const { Title } = Typography

export default function BankStatements() {
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [mappingModalOpen, setMappingModalOpen] = useState(false)
  const [selectedStatement, setSelectedStatement] = useState<any>(null)
  const [selectedCompany, setSelectedCompany] = useState<string>('')
  const queryClient = useQueryClient()

  const { data: statements, isLoading } = useQuery({ queryKey: ['bank-statements'], queryFn: bankStatementsApi.listStatements })
  const { data: accounts } = useQuery({ queryKey: ['bank-accounts'], queryFn: bankStatementsApi.listAccounts })

  // Fetch Tally companies and ledgers for bank account selection
  const { data: tallyCompanies } = useQuery({
    queryKey: ['tally-companies'],
    queryFn: tallyApi.getCompanies,
    retry: false
  })

  const { data: tallyLedgers, isLoading: ledgersLoading, refetch: refetchLedgers } = useQuery({
    queryKey: ['tally-ledgers-for-bank', selectedCompany],
    queryFn: () => tallyApi.getLedgers(selectedCompany),
    enabled: !!selectedCompany,
    retry: false
  })

  // Auto-select first company if available
  useEffect(() => {
    if (tallyCompanies?.data?.companies?.length > 0 && !selectedCompany) {
      setSelectedCompany(tallyCompanies.data.companies[0].name)
    }
  }, [tallyCompanies, selectedCompany])

  // Filter ledgers to show only bank accounts
  const bankLedgers = (tallyLedgers?.data?.ledgers || []).filter((ledger: any) =>
    ledger.parent?.toLowerCase().includes('bank') ||
    ledger.name?.toLowerCase().includes('bank')
  )

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => bankStatementsApi.uploadStatement(formData),
    onSuccess: () => { message.success('Statement uploaded and processed!'); setUploadModalOpen(false); queryClient.invalidateQueries({ queryKey: ['bank-statements'] }) },
    onError: (error: any) => message.error(error.response?.data?.error || 'Upload failed')
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => bankStatementsApi.deleteStatement(id),
    onSuccess: () => { message.success('Statement deleted'); queryClient.invalidateQueries({ queryKey: ['bank-statements'] }) },
    onError: () => message.error('Failed to delete statement')
  })

  const columns = [
    { title: 'File', dataIndex: 'original_filename', key: 'filename' },
    { title: 'Bank Account', dataIndex: ['bank_account', 'bank_name'], key: 'bank' },
    { title: 'Period', key: 'period', render: (_: any, r: any) => `${r.period_start || '-'} to ${r.period_end || '-'}` },
    { title: 'Transactions', dataIndex: 'total_transactions', key: 'transactions' },
    { title: 'Mapped', key: 'mapped', render: (_: any, r: any) => <Progress percent={r.mapping_progress || 0} size="small" style={{ width: 100 }} /> },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={{ uploaded: 'default', processing: 'blue', parsed: 'cyan', mapped: 'green', synced: 'green', failed: 'red' }[s]}>{s}</Tag> },
    {
      title: 'Actions', key: 'actions', render: (_: any, r: any) => (
        <Space>
          <Button size="small" icon={<CheckOutlined />} type="primary" onClick={() => {
            setSelectedStatement(r)
            setMappingModalOpen(true)
          }}>Map</Button>
          <Popconfirm title="Delete?" onConfirm={() => deleteMutation.mutate(r.id)} okText="Yes" cancelText="No">
            <Button size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </Space>
      )
    }
  ]

  const handleUpload = (values: any) => {
    const formData = new FormData()
    formData.append('bank_account', values.bank_account)
    formData.append('bank_ledger_name', values.tally_ledger || '') // Send Tally ledger name
    formData.append('file', values.file.file)
    uploadMutation.mutate(formData)
  }

  const handleDownloadTemplate = () => {
    window.open('/api/v1/bank-statements/template/', '_blank')
  }

  // Combine existing bank accounts with Tally ledgers
  const existingAccounts = accounts?.data?.results || accounts?.data || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>Bank Statements</Title>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>Download Template</Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>Upload Statement</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={statements?.data?.results || statements?.data || []} columns={columns} loading={isLoading} rowKey="id" />
      </Card>

      <Modal title="Upload Bank Statement" open={uploadModalOpen} onCancel={() => setUploadModalOpen(false)} footer={null} width={500}>
        <Form layout="vertical" onFinish={handleUpload}>
          {/* Tally Company Selection */}
          {tallyCompanies?.data?.companies?.length > 0 && (
            <Form.Item label="Tally Company">
              <Select
                value={selectedCompany}
                onChange={(val) => setSelectedCompany(val)}
                style={{ width: '100%' }}
              >
                {tallyCompanies.data.companies.map((c: any) => (
                  <Select.Option key={c.name} value={c.name}>{c.name}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {/* Bank Ledger from Tally */}
          <Form.Item name="tally_ledger" label="Select Bank Ledger from Tally" rules={[{ required: true, message: 'Please select a bank ledger' }]}>
            {ledgersLoading ? (
              <Spin />
            ) : bankLedgers.length > 0 ? (
              <Select placeholder="Select bank ledger" showSearch optionFilterProp="children">
                {bankLedgers.map((ledger: any) => (
                  <Select.Option key={ledger.name} value={ledger.name}>
                    {ledger.name} ({ledger.parent})
                  </Select.Option>
                ))}
              </Select>
            ) : (
              <Alert
                type="warning"
                message="No bank ledgers found"
                description={
                  <span>
                    Go to <a href="/settings">Settings → Tally Connection</a> and sync ledgers first.
                    <Button size="small" icon={<SyncOutlined />} onClick={() => refetchLedgers()} style={{ marginLeft: 8 }}>Refresh</Button>
                  </span>
                }
              />
            )}
          </Form.Item>

          {/* Existing Bank Account (if any) */}
          {existingAccounts.length > 0 && (
            <Form.Item name="bank_account" label="Or Select Existing Bank Account">
              <Select placeholder="Select existing account" allowClear>
                {existingAccounts.map((a: any) => (
                  <Select.Option key={a.id} value={a.id}>{a.bank_name} - {a.account_number}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          <Form.Item name="file" label="Statement File (CSV, Excel, or PDF)" rules={[{ required: true }]}>
            <Upload beforeUpload={() => false} accept=".pdf,.xlsx,.xls,.csv" maxCount={1}>
              <Button icon={<UploadOutlined />}>Select File</Button>
            </Upload>
          </Form.Item>
          <Form.Item><Button type="primary" htmlType="submit" loading={uploadMutation.isPending} block>Upload & Process</Button></Form.Item>
        </Form>
      </Modal>

      {selectedStatement && (
        <TransactionMapping
          open={mappingModalOpen}
          onClose={() => setMappingModalOpen(false)}
          statement={selectedStatement}
          tallyCompany={selectedCompany}
        />
      )}
    </div>
  )
}
