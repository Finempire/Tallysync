import { Card, Row, Col, Statistic, Table, Tag, Typography, Progress } from 'antd'
import { FileTextOutlined, BankOutlined, CheckCircleOutlined, SyncOutlined, WarningOutlined, ScanOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, notificationsApi } from '../api/client'

const { Title } = Typography

export default function Dashboard() {
  const { data: stats } = useQuery({ queryKey: ['dashboard-stats', 1], queryFn: () => reportsApi.getDashboardStats(1) })
  const { data: reminders } = useQuery({ queryKey: ['compliance-reminders', 1], queryFn: () => notificationsApi.getComplianceReminders(1) })

  const recentActivities = [
    { key: 1, action: 'Bank statement uploaded', status: 'success', time: '5 mins ago' },
    { key: 2, action: '15 vouchers synced to Tally', status: 'success', time: '1 hour ago' },
    { key: 3, action: 'GSTR-1 filed for November', status: 'success', time: '2 hours ago' },
    { key: 4, action: 'Payroll processed', status: 'pending', time: '3 hours ago' },
  ]

  return (
    <div>
      <Title level={4}>Dashboard</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="Bank Statements" value={stats?.data?.bank_statements?.total || 0} prefix={<BankOutlined />} suffix="processed" /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="Pending Vouchers" value={stats?.data?.vouchers?.pending || 0} prefix={<FileTextOutlined />} valueStyle={{ color: '#faad14' }} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="Synced Today" value={stats?.data?.vouchers?.synced_today || 0} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="Invoices Pending" value={stats?.data?.invoices?.pending_approval || 0} prefix={<ScanOutlined />} valueStyle={{ color: '#1890ff' }} /></Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="Recent Activity">
            <Table dataSource={recentActivities} pagination={false} size="small"
              columns={[
                { title: 'Action', dataIndex: 'action' },
                { title: 'Status', dataIndex: 'status', render: (s) => <Tag color={s === 'success' ? 'green' : 'orange'}>{s}</Tag> },
                { title: 'Time', dataIndex: 'time' }
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Tally Connection">
            <div style={{ textAlign: 'center', padding: 20 }}>
              <SyncOutlined spin style={{ fontSize: 48, color: '#52c41a' }} />
              <div style={{ marginTop: 16 }}><Tag color="green">Connected</Tag></div>
              <div style={{ marginTop: 8, color: '#888' }}>Last sync: 5 minutes ago</div>
            </div>
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="Compliance Reminders">
            {(reminders?.data?.results || reminders?.data || []).slice(0, 5).map((r: any) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span><WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />{r.compliance_type}</span>
                <span>Due: {r.due_date}</span>
              </div>
            )) || <div style={{ textAlign: 'center', color: '#888' }}>No upcoming reminders</div>}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
