import { useState } from 'react'
import { Card, Tabs, DatePicker, Button, Select, Row, Col, Statistic, Table, Typography, Space } from 'antd'
import { DownloadOutlined, BarChartOutlined, LineChartOutlined, PieChartOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, companiesApi } from '../api/client'
import dayjs from 'dayjs'

const { Title } = Typography
const { RangePicker } = DatePicker

export default function Reports() {
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([dayjs().subtract(30, 'days'), dayjs()])
  const { data: companiesResponse } = useQuery({ queryKey: ['companies'], queryFn: companiesApi.list })
  const companies = Array.isArray(companiesResponse?.data) ? companiesResponse.data : []
  const { data: trends } = useQuery({ queryKey: ['trends', 1], queryFn: () => reportsApi.getTrends(1, 30) })
  const { data: cashFlow } = useQuery({ queryKey: ['cash-flow', 1], queryFn: () => reportsApi.getCashFlowForecast(1, 30) })
  const { data: reports } = useQuery({ queryKey: ['reports', 1], queryFn: () => reportsApi.listReports(1) })

  const reportTypes = [
    { key: 'trial_balance', name: 'Trial Balance', icon: <BarChartOutlined /> },
    { key: 'profit_loss', name: 'Profit & Loss', icon: <LineChartOutlined /> },
    { key: 'gst_summary', name: 'GST Summary', icon: <PieChartOutlined /> },
    { key: 'payroll_summary', name: 'Payroll Summary', icon: <BarChartOutlined /> },
    { key: 'cash_flow', name: 'Cash Flow', icon: <LineChartOutlined /> },
  ]

  return (
    <div>
      <Title level={4}>Reports & Analytics</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <RangePicker value={dateRange} onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])} />
          <Select defaultValue={companies?.[0]?.id} style={{ width: 200 }} placeholder="Select Company">
            {companies?.map((c: any) => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}
          </Select>
        </Space>
      </Card>

      <Card>
        <Tabs defaultActiveKey="overview" items={[
          {
            key: 'overview', label: 'Overview', children: (
              <div>
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <Card title="Cash Flow Forecast" extra={<Button size="small" icon={<DownloadOutlined />}>Export</Button>}>
                      <Table dataSource={cashFlow?.data?.forecast?.slice(0, 7) || []} pagination={false} size="small" columns={[
                        { title: 'Date', dataIndex: 'date' },
                        { title: 'Inflow', dataIndex: 'expected_inflow', render: (v: number) => `₹${v?.toLocaleString()}` },
                        { title: 'Outflow', dataIndex: 'expected_outflow', render: (v: number) => `₹${v?.toLocaleString()}` },
                        { title: 'Balance', dataIndex: 'projected_balance', render: (v: number) => <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d' }}>₹{v?.toLocaleString()}</span> },
                      ]} />
                    </Card>
                  </Col>
                  <Col xs={24} lg={12}>
                    <Card title="Key Metrics">
                      <Row gutter={16}>
                        <Col span={12}><Statistic title="Total Revenue" value={125000} prefix="₹" /></Col>
                        <Col span={12}><Statistic title="Total Expenses" value={85000} prefix="₹" /></Col>
                        <Col span={12}><Statistic title="Net Profit" value={40000} prefix="₹" valueStyle={{ color: '#52c41a' }} /></Col>
                        <Col span={12}><Statistic title="Profit Margin" value={32} suffix="%" /></Col>
                      </Row>
                    </Card>
                  </Col>
                </Row>
              </div>
            )
          },
          {
            key: 'generate', label: 'Generate Reports', children: (
              <Row gutter={[16, 16]}>
                {reportTypes.map(rt => (
                  <Col xs={24} sm={12} lg={8} key={rt.key}>
                    <Card hoverable>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }}>{rt.icon}</div>
                        <Title level={5}>{rt.name}</Title>
                        <Button type="primary">Generate Report</Button>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            )
          },
          {
            key: 'history', label: 'Report History', children: (
              <Table dataSource={reports?.data || []} columns={[
                { title: 'Report Name', dataIndex: 'name' },
                { title: 'Type', dataIndex: 'report_type' },
                { title: 'Generated', dataIndex: 'generated_at', render: (d: string) => dayjs(d).format('DD/MM/YYYY HH:mm') },
                { title: 'Actions', key: 'actions', render: () => <Button size="small" icon={<DownloadOutlined />}>Download</Button> }
              ]} />
            )
          }
        ]} />
      </Card>
    </div>
  )
}
