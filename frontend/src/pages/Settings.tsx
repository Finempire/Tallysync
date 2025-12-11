import { Card, Tabs, Form, Input, Button, Switch, Select, message, Typography, Descriptions, Tag, Space, Divider, Alert, Spin, Table, Badge } from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi, notificationsApi, tallyApi } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useState } from 'react'
import { SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, CloudSyncOutlined } from '@ant-design/icons'

const { Title, Text } = Typography

export default function Settings() {
  const { user } = useAuth()
  const [profileForm] = Form.useForm()
  const [passwordForm] = Form.useForm()
  const queryClient = useQueryClient()
  const [selectedCompany, setSelectedCompany] = useState<string>('')

  const { data: prefs } = useQuery({ queryKey: ['notification-prefs'], queryFn: notificationsApi.getPreferences })
  const { data: connectors } = useQuery({ queryKey: ['connectors'], queryFn: tallyApi.listConnectors })

  // Direct Tally Connection Queries
  const { data: tallyStatus, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['tally-status'],
    queryFn: tallyApi.getStatus,
    retry: false,
    refetchInterval: 10000 // Check every 10 seconds
  })

  const { data: tallyCompanies, isLoading: companiesLoading, refetch: refetchCompanies } = useQuery({
    queryKey: ['tally-companies'],
    queryFn: tallyApi.getCompanies,
    enabled: tallyStatus?.data?.connected === true,
    retry: false
  })

  const { data: tallyLedgers, isLoading: ledgersLoading, refetch: refetchLedgers } = useQuery({
    queryKey: ['tally-ledgers', selectedCompany],
    queryFn: () => tallyApi.getLedgers(selectedCompany),
    enabled: !!selectedCompany,
    retry: false
  })

  const updateProfileMutation = useMutation({
    mutationFn: (data: any) => authApi.updateProfile(data),
    onSuccess: () => message.success('Profile updated!')
  })

  const changePasswordMutation = useMutation({
    mutationFn: (data: any) => authApi.changePassword(data),
    onSuccess: () => { message.success('Password changed!'); passwordForm.resetFields() }
  })

  const updatePrefsMutation = useMutation({
    mutationFn: (data: any) => notificationsApi.updatePreferences(data),
    onSuccess: () => message.success('Preferences updated!')
  })

  const syncLedgersMutation = useMutation({
    mutationFn: (company: string) => tallyApi.syncLedgers(company),
    onSuccess: (data) => {
      message.success(`Synced ${data.data.synced_count} ledgers from Tally!`)
      queryClient.invalidateQueries({ queryKey: ['tally-ledgers'] })
    },
    onError: (error: any) => {
      message.error(error.response?.data?.error || 'Failed to sync ledgers')
    }
  })

  const handleSyncLedgers = () => {
    if (!selectedCompany) {
      message.warning('Please select a company first')
      return
    }
    syncLedgersMutation.mutate(selectedCompany)
  }

  const ledgerColumns = [
    { title: 'Ledger Name', dataIndex: 'name', key: 'name' },
    { title: 'Parent Group', dataIndex: 'parent', key: 'parent' },
    { title: 'Opening Balance', dataIndex: 'opening_balance', key: 'opening_balance', render: (v: number) => v?.toFixed(2) },
    { title: 'Closing Balance', dataIndex: 'closing_balance', key: 'closing_balance', render: (v: number) => v?.toFixed(2) },
  ]

  return (
    <div>
      <Title level={4}>Settings</Title>

      <Card>
        <Tabs defaultActiveKey="tally" items={[
          {
            key: 'profile', label: 'Profile', children: (
              <Form form={profileForm} layout="vertical" onFinish={(v) => updateProfileMutation.mutate(v)} initialValues={user || {}}>
                <div style={{ display: 'flex', gap: 16 }}>
                  <Form.Item name="first_name" label="First Name" style={{ flex: 1 }}><Input /></Form.Item>
                  <Form.Item name="last_name" label="Last Name" style={{ flex: 1 }}><Input /></Form.Item>
                </div>
                <Form.Item name="email" label="Email"><Input disabled /></Form.Item>
                <Form.Item name="phone" label="Phone"><Input /></Form.Item>
                <Form.Item><Button type="primary" htmlType="submit" loading={updateProfileMutation.isPending}>Update Profile</Button></Form.Item>
              </Form>
            )
          },
          {
            key: 'password', label: 'Change Password', children: (
              <Form form={passwordForm} layout="vertical" onFinish={(v) => changePasswordMutation.mutate(v)} style={{ maxWidth: 400 }}>
                <Form.Item name="old_password" label="Current Password" rules={[{ required: true }]}><Input.Password /></Form.Item>
                <Form.Item name="new_password" label="New Password" rules={[{ required: true, min: 8 }]}><Input.Password /></Form.Item>
                <Form.Item name="new_password_confirm" label="Confirm New Password" dependencies={['new_password']}
                  rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, v) { return !v || getFieldValue('new_password') === v ? Promise.resolve() : Promise.reject('Passwords do not match') } })]}><Input.Password /></Form.Item>
                <Form.Item><Button type="primary" htmlType="submit" loading={changePasswordMutation.isPending}>Change Password</Button></Form.Item>
              </Form>
            )
          },
          {
            key: 'notifications', label: 'Notifications', children: (
              <Form layout="vertical" initialValues={prefs?.data} onValuesChange={(_, all) => updatePrefsMutation.mutate(all)}>
                <Title level={5}>Notification Channels</Title>
                <Form.Item name="email_enabled" label="Email Notifications" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="sms_enabled" label="SMS Notifications" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="whatsapp_enabled" label="WhatsApp Notifications" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="push_enabled" label="Push Notifications" valuePropName="checked"><Switch /></Form.Item>
                <Divider />
                <Title level={5}>Notification Types</Title>
                <Form.Item name="voucher_notifications" label="Voucher Updates" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="bank_statement_notifications" label="Bank Statement Updates" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="compliance_reminders" label="Compliance Reminders" valuePropName="checked"><Switch /></Form.Item>
                <Form.Item name="weekly_summary" label="Weekly Summary" valuePropName="checked"><Switch /></Form.Item>
              </Form>
            )
          },
          {
            key: 'tally', label: 'Tally Connection', children: (
              <div>
                <Title level={5}>Direct Tally Connection</Title>
                <Alert
                  message="Connect directly to TallyPrime"
                  description="No desktop connector needed! Make sure TallyPrime is running with ODBC Server enabled on port 9000."
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />

                {/* Connection Status */}
                <Card size="small" style={{ marginBottom: 16 }}>
                  <Space>
                    <Text strong>Tally Status:</Text>
                    {statusLoading ? (
                      <Spin size="small" />
                    ) : tallyStatus?.data?.connected ? (
                      <Badge status="success" text={<Text type="success">Connected to {tallyStatus.data.host}:{tallyStatus.data.port}</Text>} />
                    ) : (
                      <Badge status="error" text={<Text type="danger">{tallyStatus?.data?.message || 'Not Connected'}</Text>} />
                    )}
                    <Button icon={<SyncOutlined />} size="small" onClick={() => refetchStatus()}>
                      Refresh
                    </Button>
                  </Space>
                </Card>

                {/* Company Selection */}
                {tallyStatus?.data?.connected && (
                  <Card size="small" style={{ marginBottom: 16 }}>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Text strong>Select Tally Company:</Text>
                      {companiesLoading ? (
                        <Spin />
                      ) : (
                        <Select
                          style={{ width: 300 }}
                          placeholder="Select a company"
                          value={selectedCompany || undefined}
                          onChange={setSelectedCompany}
                          options={tallyCompanies?.data?.companies?.map((c: any) => ({
                            label: c.name,
                            value: c.name
                          })) || []}
                        />
                      )}
                      {tallyCompanies?.data?.count === 0 && (
                        <Alert message="No companies found in Tally. Please open a company in TallyPrime." type="warning" showIcon />
                      )}
                    </Space>
                  </Card>
                )}

                {/* Sync Actions */}
                {selectedCompany && (
                  <Card size="small" style={{ marginBottom: 16 }}>
                    <Space>
                      <Button
                        type="primary"
                        icon={<CloudSyncOutlined />}
                        loading={syncLedgersMutation.isPending}
                        onClick={handleSyncLedgers}
                      >
                        Sync Ledgers from Tally
                      </Button>
                      <Button
                        icon={<SyncOutlined />}
                        loading={ledgersLoading}
                        onClick={() => refetchLedgers()}
                      >
                        Refresh Ledgers
                      </Button>
                    </Space>
                  </Card>
                )}

                {/* Ledgers Table */}
                {selectedCompany && tallyLedgers?.data?.ledgers && (
                  <Card size="small" title={`Ledgers from ${selectedCompany} (${tallyLedgers.data.count})`}>
                    <Table
                      dataSource={tallyLedgers.data.ledgers}
                      columns={ledgerColumns}
                      rowKey="name"
                      size="small"
                      pagination={{ pageSize: 10 }}
                      loading={ledgersLoading}
                    />
                  </Card>
                )}

                <Divider />

                {/* Desktop Connector (Legacy) */}
                <Title level={5}>Desktop Connector (Optional)</Title>
                <Text type="secondary">For production deployments where the server is remote, you can use the desktop connector.</Text>
                {connectors?.data?.length > 0 ? connectors.data.map((c: any) => (
                  <Card key={c.id} style={{ marginTop: 16 }}>
                    <Descriptions column={2}>
                      <Descriptions.Item label="Name">{c.name}</Descriptions.Item>
                      <Descriptions.Item label="Status"><Tag color={c.status === 'active' ? 'green' : 'default'}>{c.status}</Tag></Descriptions.Item>
                      <Descriptions.Item label="Machine">{c.machine_name || '-'}</Descriptions.Item>
                      <Descriptions.Item label="Tally Version">{c.tally_version || '-'}</Descriptions.Item>
                      <Descriptions.Item label="Last Heartbeat">{c.last_heartbeat ? new Date(c.last_heartbeat).toLocaleString() : 'Never'}</Descriptions.Item>
                      <Descriptions.Item label="Operations">{c.successful_operations}/{c.total_operations}</Descriptions.Item>
                    </Descriptions>
                  </Card>
                )) : (
                  <Card style={{ marginTop: 16 }}>
                    <div style={{ textAlign: 'center', padding: 20 }}>
                      <p>No desktop connector configured.</p>
                      <Button href="http://localhost:8000/api/v1/tally/download-connector/" target="_blank">Download Connector</Button>
                    </div>
                  </Card>
                )}
              </div>
            )
          },
          {
            key: 'subscription', label: 'Subscription', children: (
              <Card>
                <Descriptions title="Current Plan" column={1}>
                  <Descriptions.Item label="Plan"><Tag color="blue">Professional</Tag></Descriptions.Item>
                  <Descriptions.Item label="Price">₹8,999/year</Descriptions.Item>
                  <Descriptions.Item label="Companies">3</Descriptions.Item>
                  <Descriptions.Item label="Transactions">Unlimited</Descriptions.Item>
                  <Descriptions.Item label="GST Compliance"><Tag color="green">Included</Tag></Descriptions.Item>
                  <Descriptions.Item label="E-Invoicing"><Tag color="green">Included</Tag></Descriptions.Item>
                  <Descriptions.Item label="Valid Till">Dec 31, 2025</Descriptions.Item>
                </Descriptions>
                <Space style={{ marginTop: 16 }}>
                  <Button type="primary">Upgrade Plan</Button>
                  <Button>Manage Billing</Button>
                </Space>
              </Card>
            )
          }
        ]} />
      </Card>
    </div>
  )
}
