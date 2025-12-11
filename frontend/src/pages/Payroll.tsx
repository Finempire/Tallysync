import { useState } from 'react'
import { Card, Table, Button, Tabs, Modal, Form, Input, Select, DatePicker, InputNumber, message, Tag, Space, Typography, Statistic, Row, Col } from 'antd'
import { PlusOutlined, PlayCircleOutlined, FileTextOutlined, DownloadOutlined, SyncOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { payrollApi, companiesApi } from '../api/client'
import dayjs from 'dayjs'

const { Title } = Typography

export default function Payroll() {
  const [employeeModalOpen, setEmployeeModalOpen] = useState(false)
  const [processModalOpen, setProcessModalOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: employees, isLoading: empLoading } = useQuery({ queryKey: ['employees'], queryFn: () => payrollApi.listEmployees() })
  const { data: payrollRuns } = useQuery({ queryKey: ['payroll-runs'], queryFn: payrollApi.listPayrollRuns })
  const { data: companies } = useQuery({ queryKey: ['companies'], queryFn: companiesApi.list })

  const createEmployeeMutation = useMutation({
    mutationFn: (data: any) => payrollApi.createEmployee(data),
    onSuccess: () => { message.success('Employee created!'); setEmployeeModalOpen(false); queryClient.invalidateQueries({ queryKey: ['employees'] }) }
  })

  const processPayrollMutation = useMutation({
    mutationFn: ({ companyId, month, year }: { companyId: number; month: number; year: number }) => payrollApi.processPayroll(companyId, month, year),
    onSuccess: () => { message.success('Payroll processed!'); setProcessModalOpen(false); queryClient.invalidateQueries({ queryKey: ['payroll-runs'] }) }
  })

  const employeeColumns = [
    { title: 'Code', dataIndex: 'employee_code', key: 'code' },
    { title: 'Name', key: 'name', render: (_: any, r: any) => `${r.first_name} ${r.last_name}` },
    { title: 'Department', dataIndex: 'department', key: 'department' },
    { title: 'Designation', dataIndex: 'designation', key: 'designation' },
    { title: 'CTC', dataIndex: 'ctc', key: 'ctc', render: (c: number) => `₹${c?.toLocaleString()}` },
    { title: 'Status', dataIndex: 'is_active', key: 'status', render: (a: boolean) => <Tag color={a ? 'green' : 'default'}>{a ? 'Active' : 'Inactive'}</Tag> },
    { title: 'Actions', key: 'actions', render: () => <Button size="small">View</Button> }
  ]

  const payrollColumns = [
    { title: 'Period', key: 'period', render: (_: any, r: any) => `${r.month}/${r.year}` },
    { title: 'Employees', dataIndex: 'total_employees', key: 'employees' },
    { title: 'Gross', dataIndex: 'total_gross', key: 'gross', render: (g: number) => `₹${g?.toLocaleString()}` },
    { title: 'Deductions', dataIndex: 'total_deductions', key: 'deductions', render: (d: number) => `₹${d?.toLocaleString()}` },
    { title: 'Net Pay', dataIndex: 'total_net_pay', key: 'net', render: (n: number) => `₹${n?.toLocaleString()}` },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={{ draft: 'default', processing: 'blue', processed: 'cyan', approved: 'green', paid: 'green', exported: 'purple' }[s]}>{s}</Tag> },
    {
      title: 'Actions', key: 'actions', render: (_: any, r: any) => (
        <Space>
          <Button size="small" icon={<FileTextOutlined />}>Payslips</Button>
          {r.status === 'approved' && <Button size="small" icon={<SyncOutlined />}>Export to Tally</Button>}
        </Space>
      )
    }
  ]

  return (
    <div>
      <Title level={4}>Payroll Management</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="Total Employees" value={(employees?.data?.results || employees?.data || []).length || 0} /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="Active Employees" value={(employees?.data?.results || employees?.data || []).filter((e: any) => e.is_active).length || 0} /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="Total CTC" value={(employees?.data?.results || employees?.data || []).reduce((s: number, e: any) => s + (e.ctc || 0), 0) || 0} prefix="₹" /></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card><Statistic title="Last Payroll" value={(payrollRuns?.data?.results || payrollRuns?.data || [])[0]?.status || 'N/A'} /></Card></Col>
      </Row>

      <Card>
        <Tabs defaultActiveKey="employees" items={[
          {
            key: 'employees', label: 'Employees', children: (
              <div>
                <div style={{ marginBottom: 16 }}><Button type="primary" icon={<PlusOutlined />} onClick={() => setEmployeeModalOpen(true)}>Add Employee</Button></div>
                <Table dataSource={employees?.data?.results || employees?.data || []} columns={employeeColumns} loading={empLoading} rowKey="id" />
              </div>
            )
          },
          {
            key: 'payroll', label: 'Payroll Runs', children: (
              <div>
                <div style={{ marginBottom: 16 }}><Button type="primary" icon={<PlayCircleOutlined />} onClick={() => setProcessModalOpen(true)}>Process Payroll</Button></div>
                <Table dataSource={payrollRuns?.data?.results || payrollRuns?.data || []} columns={payrollColumns} rowKey="id" />
              </div>
            )
          },
          {
            key: 'reports', label: 'Reports', children: (
              <Row gutter={16}>
                <Col span={8}><Card hoverable><Statistic title="PF ECR Report" value="Download" prefix={<DownloadOutlined />} /></Card></Col>
                <Col span={8}><Card hoverable><Statistic title="ESI Challan" value="Download" prefix={<DownloadOutlined />} /></Card></Col>
                <Col span={8}><Card hoverable><Statistic title="Form 24Q" value="Download" prefix={<DownloadOutlined />} /></Card></Col>
              </Row>
            )
          }
        ]} />
      </Card>

      <Modal title="Add Employee" open={employeeModalOpen} onCancel={() => setEmployeeModalOpen(false)} footer={null} width={700}>
        <Form layout="vertical" onFinish={(v) => createEmployeeMutation.mutate({ ...v, company: companies?.data?.[0]?.id })}>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="employee_code" label="Employee Code" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="first_name" label="First Name" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="last_name" label="Last Name" rules={[{ required: true }]}><Input /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="email" label="Email"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="phone" label="Phone"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="gender" label="Gender"><Select><Select.Option value="M">Male</Select.Option><Select.Option value="F">Female</Select.Option></Select></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="date_of_birth" label="Date of Birth" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="date_of_joining" label="Date of Joining" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="ctc" label="Annual CTC" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} prefix="₹" /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name="pan" label="PAN"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="aadhaar" label="Aadhaar"><Input /></Form.Item></Col>
            <Col span={8}><Form.Item name="uan" label="UAN"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="department" label="Department"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="designation" label="Designation"><Input /></Form.Item></Col>
          </Row>
          <Form.Item><Button type="primary" htmlType="submit" loading={createEmployeeMutation.isPending} block>Create Employee</Button></Form.Item>
        </Form>
      </Modal>

      <Modal title="Process Payroll" open={processModalOpen} onCancel={() => setProcessModalOpen(false)} footer={null}>
        <Form layout="vertical" onFinish={(v) => processPayrollMutation.mutate({ companyId: companies?.data?.[0]?.id || 1, month: v.period.month() + 1, year: v.period.year() })}>
          <Form.Item name="period" label="Payroll Period" rules={[{ required: true }]}><DatePicker picker="month" style={{ width: '100%' }} /></Form.Item>
          <Form.Item><Button type="primary" htmlType="submit" loading={processPayrollMutation.isPending} block>Process Payroll</Button></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
