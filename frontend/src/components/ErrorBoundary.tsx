import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Card, Typography, Button } from 'antd'

interface Props {
    children: ReactNode
}

interface State {
    hasError: boolean
    error: Error | null
    errorInfo: ErrorInfo | null
}

export default class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    }

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null }
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo)
        this.setState({ errorInfo })
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f2f5' }}>
                    <Card title="Something went wrong" style={{ width: 600 }}>
                        <Typography.Paragraph>
                            <Typography.Text type="danger">{this.state.error?.toString()}</Typography.Text>
                        </Typography.Paragraph>
                        <Typography.Paragraph>
                            <pre style={{ maxHeight: 200, overflow: 'auto' }}>
                                {this.state.errorInfo?.componentStack}
                            </pre>
                        </Typography.Paragraph>
                        <Button type="primary" onClick={() => window.location.reload()}>Reload Page</Button>
                    </Card>
                </div>
            )
        }

        return this.props.children
    }
}
