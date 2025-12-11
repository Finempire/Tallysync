import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Card, message, Typography } from 'antd'
import { useAuth } from '../hooks/useAuth'

const { Title, Text } = Typography

export default function Register() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { register } = useAuth()

  const onFinish = async (values: any) => {
    setLoading(true)
    try {
      await register(values)
      message.success('Registration successful!')
      navigate('/dashboard')
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5' }}>
      <Card style={{ width: 450 }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: 24 }}>Create Account</Title>
        <Form name="register" onFinish={onFinish} layout="vertical">
          <Form.Item name="tenant_name" label="Organization Name" rules={[{ required: true }]}>
            <Input placeholder="Your Company Name" />
          </Form.Item>
          <Form.Item name="subdomain" label="Subdomain" rules={[{ required: true, pattern: /^[a-z0-9-]+$/, message: 'Lowercase letters, numbers, hyphens only' }]}>
            <Input addonAfter=".tallysync.com" placeholder="yourcompany" />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}>
            <Input placeholder="admin@company.com" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item name="first_name" label="First Name" style={{ flex: 1 }}><Input /></Form.Item>
            <Form.Item name="last_name" label="Last Name" style={{ flex: 1 }}><Input /></Form.Item>
          </div>
          <Form.Item name="password" label="Password" rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="password_confirm" label="Confirm Password" dependencies={['password']}
            rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, value) { return !value || getFieldValue('password') === value ? Promise.resolve() : Promise.reject('Passwords do not match') } })]}>
            <Input.Password />
          </Form.Item>
          <Form.Item><Button type="primary" htmlType="submit" loading={loading} block size="large">Create Account</Button></Form.Item>
        </Form>
        <div style={{ textAlign: 'center' }}><Text>Already have an account? <Link to="/login">Login</Link></Text></div>
      </Card>
    </div>
  )
}
