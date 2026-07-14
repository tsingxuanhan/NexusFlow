我来为您编写一个完整的数据清洗脚本，处理这三个数据源。

```python
import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class NOAACleaner:
    """NOAA温度数据清洗器"""
    def __init__(self, data_path):
        with open(data_path, 'r') as f:
            self.raw_data = json.load(f)
    
    def parse_data(self):
        """解析NOAA温度数据"""
        records = []
        for result in self.raw_data['results']:
            # 提取年份
            date = datetime.strptime(result['date'], '%Y-%m-%dT%H:%M:%S')
            year = date.year
            
            records.append({
                'year': year,
                'date': result['date'],
                'datatype': result['datatype'],
                'station': result['station'],
                'value': result['value'],
                'attributes': result['attributes']
            })
        
        return pd.DataFrame(records)
    
    def pivot_data(self, df):
        """将温度数据转换为宽格式"""
        # 透视表：每个站点每年有TMAX和TMIN
        df_pivot = df.pivot_table(
            index=['year', 'station'],
            columns='datatype',
            values='value',
            aggfunc='mean'
        ).reset_index()
        
        # 重命名列
        df_pivot.columns.name = None
        df_pivot = df_pivot.rename(columns={
            'TMAX': 'temperature_max',
            'TMIN': 'temperature_min'
        })
        
        # 计算平均温度
        if 'temperature_max' in df_pivot.columns and 'temperature_min' in df_pivot.columns:
            df_pivot['temperature_avg'] = (df_pivot['temperature_max'] + df_pivot['temperature_min']) / 2
        
        return df_pivot

class PrecipitationCleaner:
    """NOAA降水数据清洗器"""
    def __init__(self, data_path):
        with open(data_path, 'r') as f:
            self.raw_data = json.load(f)
    
    def parse_data(self):
        """解析NOAA降水数据"""
        records = []
        for result in self.raw_data['results']:
            # 提取年份
            date = datetime.strptime(result['date'], '%Y-%m-%dT%H:%M:%S')
            year = date.year
            
            records.append({
                'year': year,
                'date': result['date'],
                'station': result['station'],
                'precipitation': result['value'],
                'attributes': result['attributes']
            })
        
        return pd.DataFrame(records)

class HealthCleaner:
    """WHO健康数据清洗器"""
    def __init__(self, data_path):
        with open(data_path, 'r') as f:
            self.raw_data = json.load(f)
    
    def parse_data(self):
        """解析WHO健康数据"""
        records = []
        for result in self.raw_data['value']:
            records.append({
                'id': result['Id'],
                'indicator_code': result['IndicatorCode'],
                'country_code': result['SpatialDim'],
                'year': result['TimeDim'],
                'sex': result.get('Dim1', ''),
                'parent_location': result.get('ParentLocation', ''),
                'value': result.get('Value', np.nan)
            })
        
        return pd.DataFrame(records)

class DataCleaner:
    """主数据清洗器"""
    def __init__(self, temperature_path, precipitation_path, health_path):
        self.temp_cleaner = NOAACleaner(temperature_path)
        self.precip_cleaner = PrecipitationCleaner(precipitation_path)
        self.health_cleaner = HealthCleaner(health_path)
        
        self.cleaning_report = {
            'original_rows': 0,
            'missing_values': 0,
            'outliers_removed': 0,
            'final_rows': 0,
            'columns': []
        }
    
    def handle_missing_values(self, df, columns, method='median'):
        """处理缺失值"""
        for col in columns:
            if col in df.columns:
                missing_count = df[col].isnull().sum()
                if missing_count > 0:
                    if method == 'median':
                        df[col].fillna(df[col].median(), inplace=True)
                    elif method == 'mean':
                        df[col].fillna(df[col].mean(), inplace=True)
                    self.cleaning_report['missing_values'] += missing_count
        return df
    
    def detect_outliers_iqr(self, df, columns):
        """IQR方法检测异常值"""
        outlier_mask = pd.Series(True, index=df.index)
        
        for col in columns:
            if col in df.columns and df[col].dtype in ['float64', 'int64']:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                col_outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
                outlier_mask = outlier_mask & ~col_outliers
                
                outliers_count = col_outliers.sum()
                if outliers_count > 0:
                    self.cleaning_report['outliers_removed'] += outliers_count
                    print(f"  列 '{col}': 发现 {outliers_count} 个异常值 (范围: [{lower_bound:.2f}, {upper_bound:.2f}])")
        
        return df[outlier_mask]
    
    def standardize_data(self, df):
        """标准化数值列"""
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        numeric_cols = [col for col in numeric_cols if col not in ['year', 'id']]
        
        for col in numeric_cols:
            if df[col].std() > 0:  # 避免除零错误
                df[f'{col}_standardized'] = (df[col] - df[col].mean()) / df[col].std()
        
        return df
    
    def merge_datasets(self):
        """合并所有数据集"""
        # 解析各个数据集
        temp_df = self.temp_cleaner.parse_data()
        temp_df = self.temp_cleaner.pivot_data(temp_df)
        
        precip_df = self.precip_cleaner.parse_data()
        health_df = self.health_cleaner.parse_data()
        
        self.cleaning_report['original_rows'] = len(temp_df) + len(precip_df) + len(health_df)
        
        # 合并温度和降水数据（按年份和站点）
        merged_df = pd.merge(temp_df, precip_df, on=['year', 'station'], how='outer')
        
        # 添加健康数据（按年份）
        health_agg = health_df.groupby('year')['value'].mean().reset_index()
        health_agg = health_agg.rename(columns={'value': 'health_indicator'})
        
        merged_df = pd.merge(merged_df, health_agg, on='year', how='left')
        
        self.cleaning_report['columns'] = list(merged_df.columns)
        
        return merged_df
    
    def clean_pipeline(self):
        """执行完整清洗流程"""
        print("=" * 60)
        print("开始数据清洗流程...")
        print("=" * 60)
        
        # 1. 合并数据集
        print("\n1. 合并数据集...")
        df = self.merge_datasets()
        print(f"   合并后数据行数: {len(df)}")
        
        # 2. 处理缺失值
        print("\n2. 处理缺失值...")
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        df = self.handle_missing_values(df, numeric_cols)
        print(f"   填充缺失值数量: {self.cleaning_report['missing_values']}")
        
        # 3. 异常值检测
        print("\n3. IQR异常值检测...")
        df = self.detect_outliers_iqr(df, numeric_cols)
        print(f"   移除异常值数量: {self.cleaning_report['outliers_removed']}")
        
        # 4. 标准化
        print("\n4. 数据标准化...")
        df = self.standardize_data(df)
        
        # 更新报告
        self.cleaning_report['final_rows'] = len(df)
        
        print("\n" + "=" * 60)
        print("清洗完成!")
        print("=" * 60)
        
        return df
    
    def save_csv(self, df, output_path='cleaned_data.csv'):
        """保存清洗后的数据到CSV"""
        df.to_csv(output_path, index=False)
        print(f"\n数据已保存至: {output_path}")
    
    def generate_report(self):
        """生成清洗报告"""
        print("\n" + "=" * 60)
        print("数据清洗报告")
        print("=" * 60)
        print(f"原始数据行数: {self.cleaning_report['original_rows']}")
        print(f"处理缺失值数量: {self.cleaning_report['missing_values']}")
        print(f"移除异常值数量: {self.cleaning_report['outliers_removed']}")
        print(f"最终数据行数: {self.cleaning_report['final_rows']}")
        print(f"数据列: {', '.join(self.cleaning_report['columns'][:10])}{'...' if len(self.cleaning_report['columns']) > 10 else ''}")
        
        # 保存报告到文件
        report_path = 'cleaning_report.txt'
        with open(report_path, 'w') as f:
            f.write("数据清洗报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"原始数据行数: {self.cleaning_report['original_rows']}\n")
            f.write(f"处理缺失值数量: {self.cleaning_report['missing_values']}\n")
            f.write(f"移除异常值数量: {self.cleaning_report['outliers_removed']}\n")
            f.write(f"最终数据行数: {self.cleaning_report['final_rows']}\n")
            f.write(f"数据列: {', '.join(self.cleaning_report['columns'])}\n")
        
        print(f"\n清洗报告已保存至: {report_path}")

def main():
    # 假设数据文件路径
    temperature_file = 'noaa_temperature.json'
    precipitation_file = 'noaa_precipitation.json'
    health_file = 'who_health.json'
    
    # 创建数据清洗器
    cleaner = DataCleaner(temperature_file, precipitation_file, health_file)
    
    # 执行清洗
    cleaned_df = cleaner.clean_pipeline()
    
    # 显示清洗后的数据摘要
    print("\n清洗后数据预览:")
    print(cleaned_df.head())
    print("\n数据统计信息:")
    print(cleaned_df.describe())
    
    # 保存结果
    cleaner.save_csv(cleaned_df)
    
    # 生成报告
    cleaner.generate_report()
    
    return cleaned_df

