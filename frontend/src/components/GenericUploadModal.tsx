
import { Modal, Form, Select, Button, Upload, message, Typography, Row, Col } from 'antd'
import { UploadOutlined, FileExcelOutlined, FilePdfOutlined, FileImageOutlined } from '@ant-design/icons'
import { useState } from 'react'

const { Text } = Typography

import { vouchersApi, companiesApi } from '../api/client'
import { useQuery, useQueryClient } from '@tanstack/react-query'

interface GenericUploadModalProps {
    open: boolean
    onCancel: () => void
    tabName: string
    companyId: number | null
}

export default function GenericUploadModal({ open, onCancel, tabName, companyId }: GenericUploadModalProps) {
    const [fileType, setFileType] = useState<'excel' | 'pdf' | 'image'>('excel')
    const [uploading, setUploading] = useState(false)
    const queryClient = useQueryClient()
    const { data: ledgers } = useQuery({
        queryKey: ['ledgers', companyId],
        queryFn: () => companiesApi.getLedgers(companyId!),
        enabled: !!companyId
    })

    // Filter ledgers
    const ledgerList = ledgers?.data?.results || ledgers?.data || []
    const salesLedgers = ledgerList.filter((l: any) => l.name.toLowerCase().includes('sale') || l.parent_name?.toLowerCase().includes('sale'))
    const taxLedgers = ledgerList.filter((l: any) => l.parent_name?.toLowerCase().includes('duties') || l.name.toLowerCase().includes('tax') || l.name.toLowerCase().includes('gst'))
    const allLedgers = ledgerList


    const handleUpload = async (values: any) => {
        if (!companyId) {
            message.error('Please select a company first')
            return
        }

        setUploading(true)
        try {
            const formData = new FormData()
            formData.append('file', values.file.file)
            formData.append('company_id', companyId.toString())
            formData.append('transaction_type', tabName.toLowerCase())
            // Pass default ledger IDs if we were using them
            if (values.default_ledger_id) formData.append('default_ledger_id', values.default_ledger_id)
            if (values.tax_ledger_ids) formData.append('tax_ledger_ids', values.tax_ledger_ids.join(','))

            await vouchersApi.import(formData)
            message.success('Vouchers imported successfully')
            queryClient.invalidateQueries({ queryKey: ['vouchers'] })
            onCancel()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Import failed')
        } finally {
            setUploading(false)
        }
    }

    return (
        <Modal title={`Upload ${tabName} Vouchers`} open={open} onCancel={onCancel} footer={null} width={600}>
            <div style={{ marginBottom: 20 }}>
                <Row gutter={16} justify="center">
                    <Col>
                        <Button
                            type={fileType === 'excel' ? 'primary' : 'default'}
                            icon={<FileExcelOutlined />}
                            onClick={() => setFileType('excel')}
                        >
                            Excel
                        </Button>
                    </Col>
                    <Col>
                        <Button
                            type={fileType === 'pdf' ? 'primary' : 'default'}
                            icon={<FilePdfOutlined />}
                            onClick={() => setFileType('pdf')}
                        >
                            PDF
                        </Button>
                    </Col>
                    <Col>
                        <Button
                            type={fileType === 'image' ? 'primary' : 'default'}
                            icon={<FileImageOutlined />}
                            onClick={() => setFileType('image')}
                        >
                            Image
                        </Button>
                    </Col>
                </Row>
            </div>

            <Form layout="vertical" onFinish={handleUpload}>
                {/* Default Ledgers Section - To be populated dynamically later */}
                {/* Default Ledgers Section */}
                <div style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, marginBottom: 16 }}>
                    <Text strong>Default Configuration</Text>
                    <Row gutter={16} style={{ marginTop: 8 }}>
                        <Col span={12}>
                            <Form.Item name="default_ledger_id" label={`${tabName} Ledger`}>
                                <Select placeholder={`Select ${tabName} Ledger`} showSearch optionFilterProp="children">
                                    {allLedgers.map((l: any) => (
                                        <Select.Option key={l.id} value={l.id}>
                                            {l.name}{l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 6, fontSize: 10 }}>✓</span>}
                                        </Select.Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        </Col>
                        <Col span={12}>
                            <Form.Item name="tax_ledger_ids" label="Tax Ledger">
                                <Select mode="multiple" placeholder="Select Tax Ledger(s)" showSearch optionFilterProp="children">
                                    {allLedgers.map((l: any) => (
                                        <Select.Option key={l.id} value={l.id}>
                                            {l.name}{l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 6, fontSize: 10 }}>✓</span>}
                                        </Select.Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        </Col>
                    </Row>
                </div>

                <Form.Item name="file" label="Select File" rules={[{ required: true }]}>
                    <Upload beforeUpload={() => false} maxCount={1}>
                        <Button icon={<UploadOutlined />} block>Click to Upload</Button>
                    </Upload>
                </Form.Item>

                <Form.Item>
                    <Button type="primary" htmlType="submit" block loading={uploading}>Processed & Import</Button>
                </Form.Item>
            </Form>
        </Modal>
    )
}
