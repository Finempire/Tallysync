/**
 * Sales Import Wizard - Suvit-style multi-step import workflow
 * Step 1: Upload & Data Type Selection
 * Step 2: Field Mapping
 * Step 3: GST Configuration
 * Step 4: Ledger Mapping (optional)
 * Step 5: Processing Screen
 */
import { useState, useEffect } from 'react'
import {
    Modal, Steps, Button, Upload, Radio, Select, Form, Table,
    Tag, Space, message, Typography, Card, Row, Col, Input,
    Tooltip, Alert, Spin
} from 'antd'
import {
    UploadOutlined, FileExcelOutlined, ArrowRightOutlined,
    CheckCircleOutlined, WarningOutlined, CloseCircleOutlined,
    PlusOutlined, SyncOutlined, EditOutlined
} from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { salesImportApi, companiesApi } from '../api/client'

const { Title, Text } = Typography
const { Step } = Steps

interface SalesImportWizardProps {
    open: boolean
    onClose: () => void
    companyId: number | null
    voucherType: string
}

export default function SalesImportWizard({ open, onClose, companyId, voucherType }: SalesImportWizardProps) {
    const [currentStep, setCurrentStep] = useState(0)
    const [importId, setImportId] = useState<number | null>(null)
    const [importType, setImportType] = useState<'with_item' | 'without_item'>('without_item')
    const [, setUploadedData] = useState<any>(null)
    const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({})
    const [gstConfig, setGstConfig] = useState<any>({})
    const [ledgerMapping, setLedgerMapping] = useState<any>({})
    const queryClient = useQueryClient()

    // Reset state when modal closes
    useEffect(() => {
        if (!open) {
            setCurrentStep(0)
            setImportId(null)
            setUploadedData(null)
            setFieldMapping({})
            setGstConfig({})
            setLedgerMapping({})
        }
    }, [open])

    const handleClose = () => {
        onClose()
        queryClient.invalidateQueries({ queryKey: ['vouchers'] })
    }

    const steps = [
        { title: 'Upload', icon: <UploadOutlined /> },
        { title: 'Field Mapping', icon: <EditOutlined /> },
        { title: 'GST Config', icon: <EditOutlined /> },
        { title: 'Ledger Mapping', icon: <EditOutlined /> },
        { title: 'Process & Push', icon: <SyncOutlined /> }
    ]

    return (
        <Modal
            title={`Import ${voucherType.charAt(0).toUpperCase() + voucherType.slice(1)} Vouchers`}
            open={open}
            onCancel={handleClose}
            width={1200}
            footer={null}
            destroyOnClose
            styles={{ body: { minHeight: 500, padding: '24px' } }}
        >
            <Steps current={currentStep} style={{ marginBottom: 24 }}>
                {steps.map((s, i) => (
                    <Step key={i} title={s.title} icon={s.icon} />
                ))}
            </Steps>

            {currentStep === 0 && (
                <UploadStep
                    companyId={companyId}
                    voucherType={voucherType}
                    importType={importType}
                    setImportType={setImportType}
                    onSuccess={(data: any) => {
                        setImportId(data.id)
                        setUploadedData(data)
                        setCurrentStep(1)
                    }}
                />
            )}

            {currentStep === 1 && importId && (
                <FieldMappingStep
                    importId={importId}
                    fieldMapping={fieldMapping}
                    setFieldMapping={setFieldMapping}
                    onBack={() => setCurrentStep(0)}
                    onNext={() => setCurrentStep(2)}
                />
            )}

            {currentStep === 2 && importId && (
                <GSTConfigStep
                    importId={importId}
                    gstConfig={gstConfig}
                    setGstConfig={setGstConfig}
                    onBack={() => setCurrentStep(1)}
                    onNext={() => setCurrentStep(3)}
                />
            )}

            {currentStep === 3 && importId && (
                <LedgerMappingStep
                    importId={importId}
                    ledgerMapping={ledgerMapping}
                    setLedgerMapping={setLedgerMapping}
                    onBack={() => setCurrentStep(2)}
                    onNext={() => setCurrentStep(4)}
                />
            )}

            {currentStep === 4 && importId && (
                <ProcessingStep
                    importId={importId}
                    companyId={companyId}
                    onBack={() => setCurrentStep(3)}
                    onComplete={handleClose}
                />
            )}
        </Modal>
    )
}

// ============================================
// STEP 1: UPLOAD
// ============================================
function UploadStep({ companyId, voucherType, importType, setImportType, onSuccess }: any) {
    const [uploading, setUploading] = useState(false)
    const [file, setFile] = useState<any>(null)

    const handleUpload = async () => {
        if (!file || !companyId) {
            message.error('Please select a file and company')
            return
        }

        setUploading(true)
        try {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('company_id', companyId.toString())
            formData.append('import_type', importType)
            formData.append('voucher_type', voucherType)

            const res = await salesImportApi.upload(formData)
            message.success(`File uploaded! Found ${res.data.total_rows} rows.`)
            onSuccess(res.data)
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Upload failed')
        } finally {
            setUploading(false)
        }
    }

    return (
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
            <Card style={{ marginBottom: 24 }}>
                <Title level={5}>Select Data Type</Title>
                <Radio.Group
                    value={importType}
                    onChange={e => setImportType(e.target.value)}
                    style={{ width: '100%' }}
                >
                    <Space direction="vertical" style={{ width: '100%' }}>
                        <Radio value="without_item" style={{ padding: '12px', background: importType === 'without_item' ? '#e6f7ff' : '#f5f5f5', borderRadius: 8, display: 'block' }}>
                            <Text strong>Without Item (Accounting Invoice)</Text>
                            <br />
                            <Text type="secondary">For service sales with no stock items. Columns: Invoice No, Date, Party, Amount, GST</Text>
                        </Radio>
                        <Radio value="with_item" style={{ padding: '12px', background: importType === 'with_item' ? '#e6f7ff' : '#f5f5f5', borderRadius: 8, display: 'block' }}>
                            <Text strong>With Item (Item Invoice)</Text>
                            <br />
                            <Text type="secondary">For product sales with stock items. Extra columns: Item Name, Qty, Rate</Text>
                        </Radio>
                    </Space>
                </Radio.Group>
            </Card>

            <Card>
                <Title level={5}>Upload Excel/CSV File</Title>
                <Upload.Dragger
                    accept=".xlsx,.xls,.csv"
                    beforeUpload={(f) => {
                        setFile(f)
                        return false
                    }}
                    onRemove={() => setFile(null)}
                    maxCount={1}
                    fileList={file ? [file] : []}
                >
                    <p className="ant-upload-drag-icon">
                        <FileExcelOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                    </p>
                    <p className="ant-upload-text">Click or drag Excel/CSV file to upload</p>
                    <p className="ant-upload-hint">Supports .xlsx, .xls, .csv formats</p>
                </Upload.Dragger>

                <Button
                    type="primary"
                    size="large"
                    block
                    style={{ marginTop: 24 }}
                    loading={uploading}
                    disabled={!file}
                    onClick={handleUpload}
                    icon={<ArrowRightOutlined />}
                >
                    Upload & Continue
                </Button>
            </Card>
        </div>
    )
}

// ============================================
// STEP 2: FIELD MAPPING
// ============================================
function FieldMappingStep({ importId, fieldMapping, setFieldMapping, onBack, onNext }: any) {
    const [saving, setSaving] = useState(false)

    const { data, isLoading } = useQuery({
        queryKey: ['sales-import-field-mapping', importId],
        queryFn: () => salesImportApi.getFieldMapping(importId)
    })

    const mappingData = data?.data || {}
    const detectedColumns = mappingData.detected_columns || []
    const sampleData = mappingData.sample_data || []
    const availableFields = mappingData.available_fields || []

    // Auto-suggest mappings based on column names
    useEffect(() => {
        if (detectedColumns.length > 0 && Object.keys(fieldMapping).length === 0) {
            const autoMapping: Record<string, string> = {}
            detectedColumns.forEach((col: string) => {
                const colLower = col.toLowerCase()
                // Simple auto-mapping logic
                if (colLower.includes('date')) autoMapping[col] = 'date'
                else if (colLower.includes('party') || colLower.includes('customer') || colLower.includes('vendor')) autoMapping[col] = 'party_name'
                else if (colLower.includes('invoice') && colLower.includes('no')) autoMapping[col] = 'reference_no'
                else if (colLower.includes('amount') && !colLower.includes('cgst') && !colLower.includes('sgst')) autoMapping[col] = 'amount'
                else if (colLower.includes('cgst')) autoMapping[col] = 'cgst'
                else if (colLower.includes('sgst')) autoMapping[col] = 'sgst'
                else if (colLower.includes('igst')) autoMapping[col] = 'igst'
                else if (colLower.includes('item') || colLower.includes('product')) autoMapping[col] = 'item_name'
                else if (colLower.includes('qty') || colLower.includes('quantity')) autoMapping[col] = 'quantity'
                else if (colLower.includes('rate') || colLower.includes('price')) autoMapping[col] = 'rate'
                else if (colLower.includes('narration') || colLower.includes('remark')) autoMapping[col] = 'narration'
            })
            setFieldMapping(autoMapping)
        }
    }, [detectedColumns])

    const handleSave = async () => {
        // Check required fields
        const requiredFields = availableFields.filter((f: any) => f.required).map((f: any) => f.key)
        const mappedFields = Object.values(fieldMapping)
        const missingRequired = requiredFields.filter((f: string) => !mappedFields.includes(f))

        if (missingRequired.length > 0) {
            message.error(`Please map required fields: ${missingRequired.join(', ')}`)
            return
        }

        setSaving(true)
        try {
            await salesImportApi.saveFieldMapping(importId, fieldMapping)
            message.success('Field mapping saved')
            onNext()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Failed to save mapping')
        } finally {
            setSaving(false)
        }
    }

    if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

    return (
        <div>
            <Alert
                message="Map your Excel columns to Tally fields"
                description="Required fields are marked with *. We've auto-detected some mappings for you."
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
            />

            <Row gutter={24}>
                <Col span={14}>
                    <Card title="Column Mapping" size="small">
                        <Table
                            dataSource={detectedColumns.map((col: string, idx: number) => ({
                                key: idx,
                                column: col,
                                sample: sampleData[0]?.[col] || ''
                            }))}
                            columns={[
                                {
                                    title: 'Excel Column',
                                    dataIndex: 'column',
                                    width: 150,
                                    render: (col: string) => <Text code>{col}</Text>
                                },
                                {
                                    title: 'Sample Data',
                                    dataIndex: 'sample',
                                    width: 150,
                                    render: (val: any) => <Text type="secondary">{String(val).substring(0, 30)}</Text>
                                },
                                {
                                    title: 'Map To (Tally Field)',
                                    width: 200,
                                    render: (_: any, record: any) => (
                                        <Select
                                            value={fieldMapping[record.column]}
                                            onChange={(val) => setFieldMapping({ ...fieldMapping, [record.column]: val })}
                                            placeholder="Select field..."
                                            allowClear
                                            style={{ width: '100%' }}
                                            showSearch
                                            optionFilterProp="children"
                                        >
                                            {availableFields.map((f: any) => (
                                                <Select.Option key={f.key} value={f.key}>
                                                    {f.label} {f.required && <Text type="danger">*</Text>}
                                                </Select.Option>
                                            ))}
                                        </Select>
                                    )
                                }
                            ]}
                            pagination={false}
                            scroll={{ y: 350 }}
                            size="small"
                        />
                    </Card>
                </Col>

                <Col span={10}>
                    <Card title="Data Preview" size="small">
                        <div style={{ maxHeight: 400, overflow: 'auto' }}>
                            {sampleData.slice(0, 3).map((row: any, idx: number) => (
                                <Card key={idx} size="small" style={{ marginBottom: 8 }} type="inner" title={`Row ${idx + 1}`}>
                                    {Object.entries(row).slice(0, 6).map(([k, v]) => (
                                        <div key={k} style={{ marginBottom: 4 }}>
                                            <Text type="secondary">{k}: </Text>
                                            <Text>{String(v)}</Text>
                                        </div>
                                    ))}
                                </Card>
                            ))}
                        </div>
                    </Card>
                </Col>
            </Row>

            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={onBack}>Back</Button>
                <Button type="primary" onClick={handleSave} loading={saving} icon={<ArrowRightOutlined />}>
                    Save & Continue
                </Button>
            </div>
        </div>
    )
}

// ============================================
// STEP 3: GST CONFIG
// ============================================
function GSTConfigStep({ importId, gstConfig, setGstConfig, onBack, onNext }: any) {
    const [saving, setSaving] = useState(false)

    const { data, isLoading } = useQuery({
        queryKey: ['sales-import-gst-config', importId],
        queryFn: () => salesImportApi.getGSTConfig(importId)
    })

    const configData = data?.data || {}
    const taxLedgers = configData.tax_ledgers || []

    const handleSave = async () => {
        setSaving(true)
        try {
            await salesImportApi.saveGSTConfig(importId, gstConfig)
            message.success('GST configuration saved')
            onNext()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Failed to save config')
        } finally {
            setSaving(false)
        }
    }

    if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

    return (
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
            <Card title="GST Calculation Method">
                <Radio.Group
                    value={gstConfig.method || 'from_excel'}
                    onChange={e => setGstConfig({ ...gstConfig, method: e.target.value })}
                    style={{ width: '100%' }}
                >
                    <Space direction="vertical" style={{ width: '100%' }}>
                        <Radio value="from_excel" style={{ padding: 12, background: '#f5f5f5', borderRadius: 8, display: 'block' }}>
                            <Text strong>Take GST values from Excel</Text>
                            <br />
                            <Text type="secondary">Use CGST, SGST, IGST columns from your uploaded file</Text>
                        </Radio>
                        <Radio value="auto_calculate" style={{ padding: 12, background: '#f5f5f5', borderRadius: 8, display: 'block' }}>
                            <Text strong>Auto-calculate GST</Text>
                            <br />
                            <Text type="secondary">System calculates GST based on rate you specify</Text>
                        </Radio>
                        <Radio value="no_gst" style={{ padding: 12, background: '#f5f5f5', borderRadius: 8, display: 'block' }}>
                            <Text strong>No GST applicable</Text>
                            <br />
                            <Text type="secondary">Skip GST calculation for these invoices</Text>
                        </Radio>
                    </Space>
                </Radio.Group>

                {gstConfig.method === 'auto_calculate' && (
                    <div style={{ marginTop: 24 }}>
                        <Row gutter={16}>
                            <Col span={12}>
                                <Form.Item label="GST Rate (%)">
                                    <Select
                                        value={gstConfig.gst_rate}
                                        onChange={val => setGstConfig({ ...gstConfig, gst_rate: val })}
                                        placeholder="Select GST rate"
                                    >
                                        <Select.Option value={5}>5%</Select.Option>
                                        <Select.Option value={12}>12%</Select.Option>
                                        <Select.Option value={18}>18%</Select.Option>
                                        <Select.Option value={28}>28%</Select.Option>
                                    </Select>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item label="Tax Type">
                                    <Radio.Group
                                        value={gstConfig.is_igst}
                                        onChange={e => setGstConfig({ ...gstConfig, is_igst: e.target.value })}
                                    >
                                        <Radio value={false}>CGST + SGST (Intra-state)</Radio>
                                        <Radio value={true}>IGST (Inter-state)</Radio>
                                    </Radio.Group>
                                </Form.Item>
                            </Col>
                        </Row>
                    </div>
                )}
            </Card>

            <Card title="Tax Ledger Selection" style={{ marginTop: 16 }}>
                <Row gutter={16}>
                    <Col span={8}>
                        <Form.Item label="CGST Ledger">
                            <Select
                                value={gstConfig.cgst_ledger}
                                onChange={val => setGstConfig({ ...gstConfig, cgst_ledger: val })}
                                placeholder="Select CGST ledger"
                                allowClear
                                showSearch
                                optionFilterProp="children"
                            >
                                {taxLedgers.map((l: any) => (
                                    <Select.Option key={l.id} value={l.id}>
                                        {l.name}{l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 8, fontSize: 11 }}>✓ Synced</span>}
                                    </Select.Option>
                                ))}
                            </Select>
                        </Form.Item>
                    </Col>
                    <Col span={8}>
                        <Form.Item label="SGST Ledger">
                            <Select
                                value={gstConfig.sgst_ledger}
                                onChange={val => setGstConfig({ ...gstConfig, sgst_ledger: val })}
                                placeholder="Select SGST ledger"
                                allowClear
                                showSearch
                                optionFilterProp="children"
                            >
                                {taxLedgers.map((l: any) => (
                                    <Select.Option key={l.id} value={l.id}>
                                        {l.name}{l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 8, fontSize: 11 }}>✓ Synced</span>}
                                    </Select.Option>
                                ))}
                            </Select>
                        </Form.Item>
                    </Col>
                    <Col span={8}>
                        <Form.Item label="IGST Ledger">
                            <Select
                                value={gstConfig.igst_ledger}
                                onChange={val => setGstConfig({ ...gstConfig, igst_ledger: val })}
                                placeholder="Select IGST ledger"
                                allowClear
                                showSearch
                                optionFilterProp="children"
                            >
                                {taxLedgers.map((l: any) => (
                                    <Select.Option key={l.id} value={l.id}>
                                        {l.name}{l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 8, fontSize: 11 }}>✓ Synced</span>}
                                    </Select.Option>
                                ))}
                            </Select>
                        </Form.Item>
                    </Col>
                </Row>
            </Card>

            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={onBack}>Back</Button>
                <Button type="primary" onClick={handleSave} loading={saving} icon={<ArrowRightOutlined />}>
                    Save & Continue
                </Button>
            </div>
        </div>
    )
}

// ============================================
// STEP 4: LEDGER MAPPING
// ============================================
function LedgerMappingStep({ importId, ledgerMapping, setLedgerMapping, onBack, onNext }: any) {
    const [saving, setSaving] = useState(false)

    const { data, isLoading } = useQuery({
        queryKey: ['sales-import-ledger-mapping', importId],
        queryFn: () => salesImportApi.getLedgerMapping(importId)
    })

    const mappingData = data?.data || {}
    const unmappedColumns = mappingData.unmapped_columns || []
    const availableLedgers = mappingData.available_ledgers || []

    const handleSave = async () => {
        setSaving(true)
        try {
            await salesImportApi.saveLedgerMapping(importId, ledgerMapping)
            message.success('Ledger mapping saved')
            onNext()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Failed to save mapping')
        } finally {
            setSaving(false)
        }
    }

    if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

    return (
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
            <Alert
                message="Map Additional Columns to Ledgers (Optional)"
                description="If you have columns like Freight, Discount, Round-off, map them to appropriate ledgers."
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
            />

            {unmappedColumns.length === 0 ? (
                <Card>
                    <Text>All columns have been mapped. You can proceed to the next step.</Text>
                </Card>
            ) : (
                <Card>
                    <Table
                        dataSource={unmappedColumns.map((col: string, idx: number) => ({
                            key: idx,
                            column: col
                        }))}
                        columns={[
                            {
                                title: 'Unmapped Column',
                                dataIndex: 'column',
                                render: (col: string) => <Text code>{col}</Text>
                            },
                            {
                                title: 'Map to Ledger',
                                render: (_: any, record: any) => (
                                    <Select
                                        value={ledgerMapping[record.column]}
                                        onChange={val => setLedgerMapping({ ...ledgerMapping, [record.column]: val })}
                                        placeholder="Select ledger..."
                                        allowClear
                                        style={{ width: 300 }}
                                        showSearch
                                        optionFilterProp="children"
                                    >
                                        {availableLedgers.map((l: any) => (
                                            <Select.Option key={l.id} value={l.id}>
                                                {l.name} ({l.ledger_group}){l.synced_from_tally && <span style={{ color: '#52c41a', marginLeft: 6, fontSize: 10 }}>✓</span>}
                                            </Select.Option>
                                        ))}
                                    </Select>
                                )
                            }
                        ]}
                        pagination={false}
                        size="small"
                    />
                </Card>
            )}

            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={onBack}>Back</Button>
                <Space>
                    <Button onClick={onNext}>Skip</Button>
                    <Button type="primary" onClick={handleSave} loading={saving} icon={<ArrowRightOutlined />}>
                        Save & Continue
                    </Button>
                </Space>
            </div>
        </div>
    )
}

// ============================================
// STEP 5: PROCESSING SCREEN
// ============================================
function ProcessingStep({ importId, companyId, onBack, onComplete }: any) {
    const [selectedRows, setSelectedRows] = useState<number[]>([])
    const [statusFilter, setStatusFilter] = useState<string>('')
    const [processing, setProcessing] = useState(false)
    const [pushing, setPushing] = useState(false)
    const [createPartyModal, setCreatePartyModal] = useState<any>(null)
    const queryClient = useQueryClient()

    const { data, isLoading, refetch } = useQuery({
        queryKey: ['sales-import-rows', importId, statusFilter],
        queryFn: () => salesImportApi.getRows(importId, statusFilter || undefined)
    })

    const { data: ledgersData } = useQuery({
        queryKey: ['ledgers', companyId],
        queryFn: () => companiesApi.getLedgers(companyId!),
        enabled: !!companyId
    })

    const rowsData = data?.data || {}
    const rows = rowsData.rows || []
    const stats = rowsData.stats || {}
    const ledgers = ledgersData?.data?.results || ledgersData?.data || []

    const handleUpdateRow = async (rowId: number, partyLedgerId: number) => {
        try {
            await salesImportApi.updateRow(importId, rowId, { party_ledger_id: partyLedgerId })
            message.success('Row updated')
            refetch()
        } catch (error) {
            message.error('Failed to update row')
        }
    }

    const handleProcess = async () => {
        setProcessing(true)
        try {
            const rowIds = selectedRows.length > 0 ? selectedRows : undefined
            const res = await salesImportApi.process(importId, rowIds)
            message.success(`${res.data.created_count} vouchers created`)
            if (res.data.errors?.length > 0) {
                message.warning(`${res.data.errors.length} rows had errors`)
            }
            refetch()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Processing failed')
        } finally {
            setProcessing(false)
        }
    }

    const handlePushToTally = async () => {
        setPushing(true)
        try {
            const rowIds = selectedRows.length > 0 ? selectedRows : undefined
            const res = await salesImportApi.pushToTally(importId, rowIds)
            message.success(res.data.message)
            refetch()
            queryClient.invalidateQueries({ queryKey: ['vouchers'] })
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Push failed')
        } finally {
            setPushing(false)
        }
    }

    const handleCreateParty = async (values: any) => {
        try {
            await salesImportApi.createParty(importId, {
                name: values.name,
                gstin: values.gstin,
                row_ids: createPartyModal.rowIds
            })
            message.success('Party created')
            setCreatePartyModal(null)
            refetch()
        } catch (error: any) {
            message.error(error.response?.data?.error || 'Failed to create party')
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'valid': return 'success'
            case 'warning': return 'warning'
            case 'error': return 'error'
            case 'processed': return 'processing'
            case 'synced': return 'purple'
            default: return 'default'
        }
    }

    const columns = [
        {
            title: '#',
            dataIndex: 'row_number',
            width: 50,
            fixed: 'left' as const
        },
        {
            title: 'Status',
            dataIndex: 'validation_status',
            width: 100,
            render: (status: string) => (
                <Tag color={getStatusColor(status)}>
                    {status === 'valid' && <CheckCircleOutlined />}
                    {status === 'warning' && <WarningOutlined />}
                    {status === 'error' && <CloseCircleOutlined />}
                    {' '}{status.toUpperCase()}
                </Tag>
            )
        },
        {
            title: 'Date',
            dataIndex: ['mapped_data', 'date'],
            width: 100
        },
        {
            title: 'Party Name',
            dataIndex: ['mapped_data', 'party_name'],
            width: 150,
            ellipsis: true
        },
        {
            title: 'Party Ledger',
            width: 180,
            render: (_: any, record: any) => (
                record.party_ledger_name ? (
                    <Tag color="green">{record.party_ledger_name}</Tag>
                ) : (
                    <Space>
                        <Select
                            style={{ width: 120 }}
                            placeholder="Select..."
                            size="small"
                            showSearch
                            optionFilterProp="children"
                            onChange={(val) => handleUpdateRow(record.id, val)}
                        >
                            {ledgers.map((l: any) => (
                                <Select.Option key={l.id} value={l.id}>{l.name}</Select.Option>
                            ))}
                        </Select>
                        <Tooltip title="Create New Party">
                            <Button
                                size="small"
                                icon={<PlusOutlined />}
                                onClick={() => setCreatePartyModal({
                                    name: record.mapped_data?.party_name,
                                    rowIds: [record.id]
                                })}
                            />
                        </Tooltip>
                    </Space>
                )
            )
        },
        {
            title: 'Amount',
            dataIndex: ['mapped_data', 'amount'],
            width: 100,
            render: (val: any) => val ? `₹${Number(val).toLocaleString()}` : '-'
        },
        {
            title: 'Errors/Warnings',
            width: 200,
            render: (_: any, record: any) => (
                <Space direction="vertical" size={0}>
                    {record.validation_errors?.map((e: string, i: number) => (
                        <Text key={i} type="danger" style={{ fontSize: 12 }}>{e}</Text>
                    ))}
                    {record.validation_warnings?.map((w: string, i: number) => (
                        <Text key={i} type="warning" style={{ fontSize: 12 }}>{w}</Text>
                    ))}
                </Space>
            )
        },
        {
            title: 'Voucher',
            width: 100,
            render: (_: any, record: any) => (
                record.voucher_id ? (
                    <Tag color={record.voucher_status === 'synced' ? 'purple' : 'blue'}>
                        #{record.voucher_id}
                    </Tag>
                ) : '-'
            )
        }
    ]

    if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

    return (
        <div>
            {/* Stats Bar */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={4}>
                    <Card size="small">
                        <Statistic title="Total" value={rowsData.total_rows || 0} />
                    </Card>
                </Col>
                <Col span={4}>
                    <Card size="small" style={{ borderTop: '3px solid #52c41a' }}>
                        <Statistic title="Valid" value={stats.valid || 0} valueStyle={{ color: '#52c41a' }} />
                    </Card>
                </Col>
                <Col span={4}>
                    <Card size="small" style={{ borderTop: '3px solid #faad14' }}>
                        <Statistic title="Warning" value={stats.warning || 0} valueStyle={{ color: '#faad14' }} />
                    </Card>
                </Col>
                <Col span={4}>
                    <Card size="small" style={{ borderTop: '3px solid #ff4d4f' }}>
                        <Statistic title="Error" value={stats.error || 0} valueStyle={{ color: '#ff4d4f' }} />
                    </Card>
                </Col>
                <Col span={4}>
                    <Card size="small" style={{ borderTop: '3px solid #1890ff' }}>
                        <Statistic title="Processed" value={stats.processed || 0} valueStyle={{ color: '#1890ff' }} />
                    </Card>
                </Col>
                <Col span={4}>
                    <Card size="small" style={{ borderTop: '3px solid #722ed1' }}>
                        <Statistic title="Synced" value={stats.synced || 0} valueStyle={{ color: '#722ed1' }} />
                    </Card>
                </Col>
            </Row>

            {/* Filter & Actions */}
            <Space style={{ marginBottom: 16 }}>
                <Select
                    value={statusFilter}
                    onChange={setStatusFilter}
                    style={{ width: 150 }}
                    placeholder="Filter by status"
                    allowClear
                >
                    <Select.Option value="valid">Valid</Select.Option>
                    <Select.Option value="warning">Warning</Select.Option>
                    <Select.Option value="error">Error</Select.Option>
                    <Select.Option value="processed">Processed</Select.Option>
                    <Select.Option value="synced">Synced</Select.Option>
                </Select>

                {selectedRows.length > 0 && (
                    <Text type="secondary">{selectedRows.length} rows selected</Text>
                )}

                <Button onClick={() => refetch()}>Refresh</Button>
                <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    onClick={handleProcess}
                    loading={processing}
                    disabled={rows.filter((r: any) => ['valid', 'warning'].includes(r.validation_status)).length === 0}
                >
                    Create Vouchers {selectedRows.length > 0 ? `(${selectedRows.length})` : ''}
                </Button>
                <Button
                    type="primary"
                    style={{ background: '#722ed1' }}
                    icon={<SyncOutlined />}
                    onClick={handlePushToTally}
                    loading={pushing}
                    disabled={rows.filter((r: any) => r.validation_status === 'processed').length === 0}
                >
                    Push to Tally {selectedRows.length > 0 ? `(${selectedRows.length})` : ''}
                </Button>
            </Space>

            {/* Data Table */}
            <Table
                dataSource={rows}
                columns={columns}
                rowKey="id"
                size="small"
                scroll={{ x: 1000, y: 350 }}
                pagination={{ pageSize: 50, showSizeChanger: true }}
                rowSelection={{
                    selectedRowKeys: selectedRows,
                    onChange: (keys) => setSelectedRows(keys as number[])
                }}
                rowClassName={(record: any) => {
                    if (record.validation_status === 'valid') return 'row-valid'
                    if (record.validation_status === 'warning') return 'row-warning'
                    if (record.validation_status === 'error') return 'row-error'
                    return ''
                }}
            />

            {/* Actions */}
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={onBack}>Back</Button>
                <Button type="primary" onClick={onComplete}>Done</Button>
            </div>

            {/* Create Party Modal */}
            <Modal
                title="Create New Party Ledger"
                open={!!createPartyModal}
                onCancel={() => setCreatePartyModal(null)}
                footer={null}
            >
                <Form layout="vertical" onFinish={handleCreateParty} initialValues={{ name: createPartyModal?.name }}>
                    <Form.Item name="name" label="Party Name" rules={[{ required: true }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="gstin" label="GSTIN">
                        <Input placeholder="Optional" />
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit" block>Create Party</Button>
                    </Form.Item>
                </Form>
            </Modal>

            <style>{`
        .row-valid { background-color: #f6ffed; }
        .row-warning { background-color: #fffbe6; }
        .row-error { background-color: #fff2f0; }
      `}</style>
        </div>
    )
}

// Simple Statistic component
function Statistic({ title, value, valueStyle }: { title: string, value: number, valueStyle?: any }) {
    return (
        <div>
            <Text type="secondary" style={{ fontSize: 12 }}>{title}</Text>
            <div style={{ fontSize: 24, fontWeight: 600, ...valueStyle }}>{value}</div>
        </div>
    )
}
