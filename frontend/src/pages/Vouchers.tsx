import { useState, useEffect } from 'react'
import { Card, Button, Modal, Form, Input, Select, DatePicker, InputNumber, message, Space, Typography, Drawer, Tabs, Radio } from 'antd'
import { CheckOutlined, SyncOutlined, CloudUploadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vouchersApi, companiesApi, tallyApi } from '../api/client'
import VoucherList from '../components/VoucherList'
import SalesImportWizard from '../components/SalesImportWizard'
import VoucherMappingModal from '../components/VoucherMappingModal'

const { Title } = Typography

export default function Vouchers() {
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [xmlPreview, setXmlPreview] = useState<string | null>(null)
  const [mappingVoucher, setMappingVoucher] = useState<any>(null)
  const [selectedRows, setSelectedRows] = useState<number[]>([])
  const [activeTab, setActiveTab] = useState('sales')
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')

  const queryClient = useQueryClient()

  // Use synced Tally companies
  const { data: tallyCompanies } = useQuery({
    queryKey: ['tallyCompanies'],
    queryFn: tallyApi.getCompanies
  })

  // Get database companies for matching IDs
  const { data: companies } = useQuery({ queryKey: ['companies'], queryFn: companiesApi.list })

  // Build merged company list from Tally and database
  const rawTallyList = tallyCompanies?.data?.companies || tallyCompanies?.data || []
  const dbCompanyList = companies?.data?.results || companies?.data || []

  // Create merged list - use Tally company names but match with DB for IDs
  // Handle both cases: tallyItem could be a string or an object with name property
  const companyList = rawTallyList.map((tallyItem: any, index: number) => {
    const tallyName = typeof tallyItem === 'string' ? tallyItem : tallyItem?.name || tallyItem
    const dbMatch = dbCompanyList.find((c: any) => c.name === tallyName || c.tally_company === tallyName)
    return {
      id: dbMatch?.id || index + 1,
      name: String(tallyName)
    }
  })

  // Auto-select first Tally company if available
  useEffect(() => {
    if (!selectedCompany && companyList.length > 0) {
      setSelectedCompany(companyList[0].id)
    }
  }, [companyList, selectedCompany])

  // TODO: Add filters to API based on activeTab
  const { data: vouchers, isLoading } = useQuery({
    queryKey: ['vouchers', activeTab, selectedCompany, statusFilter],
    queryFn: () => vouchersApi.list({
      type: activeTab,
      company: selectedCompany,
      status: statusFilter === 'all' ? undefined : statusFilter
    }),
    enabled: !!selectedCompany // Only fetch if company is selected
  })

  const approveMutation = useMutation({
    mutationFn: (ids: number[]) => vouchersApi.bulkApprove(ids),
    onSuccess: () => { message.success('Vouchers approved!'); queryClient.invalidateQueries({ queryKey: ['vouchers'] }); setSelectedRows([]) }
  })

  const pushToTallyMutation = useMutation({
    mutationFn: (ids: number[]) => vouchersApi.bulkPushToTally(ids),
    onSuccess: () => { message.success('Vouchers queued for Tally sync!'); queryClient.invalidateQueries({ queryKey: ['vouchers'] }); setSelectedRows([]) }
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => vouchersApi.delete(id),
    onSuccess: () => { message.success('Voucher deleted!'); queryClient.invalidateQueries({ queryKey: ['vouchers'] }) }
  })

  const getXmlPreview = async (id: number) => {
    const res = await vouchersApi.getXmlPreview(id);
    setXmlPreview(res.data.xml)
  }

  const handleMap = (voucher: any) => {
    setMappingVoucher(voucher)
  }

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id)
  }

  const tabItems = [
    {
      key: 'sales',
      label: 'Sales',
      children: <VoucherList data={vouchers?.data?.results || []} isLoading={isLoading} onViewXml={getXmlPreview} onSync={(ids) => pushToTallyMutation.mutate(ids)} selectedRows={selectedRows} setSelectedRows={setSelectedRows} onMap={handleMap} onDelete={handleDelete} />
    },
    {
      key: 'purchase',
      label: 'Purchase',
      children: <VoucherList data={vouchers?.data?.results || []} isLoading={isLoading} onViewXml={getXmlPreview} onSync={(ids) => pushToTallyMutation.mutate(ids)} selectedRows={selectedRows} setSelectedRows={setSelectedRows} onMap={handleMap} onDelete={handleDelete} />
    },
    {
      key: 'journal',
      label: 'Journal',
      children: <VoucherList data={vouchers?.data?.results || []} isLoading={isLoading} onViewXml={getXmlPreview} onSync={(ids) => pushToTallyMutation.mutate(ids)} selectedRows={selectedRows} setSelectedRows={setSelectedRows} onMap={handleMap} onDelete={handleDelete} />
    },

  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={4} style={{ marginBottom: 0 }}>Voucher Management</Title>
          <Select
            style={{ width: 280 }}
            placeholder="Select Tally Company"
            onChange={setSelectedCompany}
            value={selectedCompany}
            notFoundContent={companyList.length === 0 ? "Connect Tally to see companies" : undefined}
          >
            {companyList.map((c: any) => (
              <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>
            ))}
          </Select>
        </Space>
        <Space>
          {selectedRows.length > 0 && (
            <>
              <Button icon={<CheckOutlined />} onClick={() => approveMutation.mutate(selectedRows)}>Approve ({selectedRows.length})</Button>
              <Button type="primary" icon={<SyncOutlined />} onClick={() => pushToTallyMutation.mutate(selectedRows)}>Sync to Tally</Button>
            </>
          )}
          <Button icon={<CloudUploadOutlined />} onClick={() => setUploadModalOpen(true)}>Bulk Upload</Button>
          <Button icon={<CloudUploadOutlined />} onClick={async () => {
            try {
              const response = await vouchersApi.downloadTemplate(activeTab)
              const url = window.URL.createObjectURL(new Blob([response.data]));
              const link = document.createElement('a');
              link.href = url;
              link.setAttribute('download', `${activeTab}_template.xlsx`);
              document.body.appendChild(link);
              link.click();
              link.remove();
            } catch (e) {
              message.error('Failed to download template')
            }
          }}>Download Template</Button>
        </Space>
      </div>

      <Card bodyStyle={{ padding: '0 10px 10px' }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          tabBarStyle={{ marginBottom: 16, marginTop: 10 }}
          tabBarExtraContent={
            <Radio.Group value={statusFilter} onChange={e => setStatusFilter(e.target.value)} buttonStyle="solid">
              <Radio.Button value="all">All</Radio.Button>
              <Radio.Button value="unverified">Unverified</Radio.Button>
              <Radio.Button value="draft">Draft</Radio.Button>
              <Radio.Button value="approved">Verified</Radio.Button>
              <Radio.Button value="error">Error</Radio.Button>
            </Radio.Group>
          }
        />
      </Card>

      <Drawer title="Tally XML Preview" open={!!xmlPreview} onClose={() => setXmlPreview(null)} width={600}>
        <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 4, overflow: 'auto', fontSize: 12 }}>{xmlPreview}</pre>
      </Drawer>

      <VoucherMappingModal
        open={!!mappingVoucher}
        onCancel={() => setMappingVoucher(null)}
        voucher={mappingVoucher}
      />

      <SalesImportWizard
        open={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        companyId={selectedCompany}
        voucherType={activeTab}
      />

      <Modal title="Create Voucher" open={createModalOpen} onCancel={() => setCreateModalOpen(false)} footer={null} width={600}>
        <Form layout="vertical">
          <Form.Item name="company" label="Company" rules={[{ required: true }]}>
            <Select placeholder="Select company">{companyList.map((c: any) => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}</Select>
          </Form.Item>
          <Form.Item name="voucher_type" label="Voucher Type" rules={[{ required: true }]}>
            <Select placeholder="Select type">
              <Select.Option value="payment">Payment</Select.Option>
              <Select.Option value="receipt">Receipt</Select.Option>
              <Select.Option value="journal">Journal</Select.Option>
              <Select.Option value="contra">Contra</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="date" label="Date" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="amount" label="Amount" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} prefix="₹" /></Form.Item>
          <Form.Item name="narration" label="Narration"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item><Button type="primary" htmlType="submit" block>Create Voucher</Button></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

