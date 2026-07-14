我来编写一个完整的多元回归分析Python脚本，使用纯NumPy实现所有统计计算。

```python
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class MultipleLinearRegression:
    """
    多元线性回归分析类
    使用纯NumPy实现，不依赖sklearn
    """
    
    def __init__(self):
        self.coefficients = None
        self.intercept = None
        self.residuals = None
        self.fitted_values = None
        self.r_squared = None
        self.adj_r_squared = None
        self.mse = None
        self.t_stats = None
        self.p_values = None
        self.std_errors = None
        self.cov_matrix = None
        
    def fit(self, X, y):
        """
        拟合OLS回归模型
        X: 自变量矩阵 (n_samples, n_features)
        y: 因变量向量 (n_samples,)
        """
        # 添加截距项
        X_with_intercept = np.column_stack([np.ones(X.shape[0]), X])
        
        # OLS估计: β = (X'X)^(-1)X'y
        XTX = X_with_intercept.T @ X_with_intercept
        XTX_inv = np.linalg.inv(XTX)
        XTy = X_with_intercept.T @ y
        
        # 回归系数
        beta = XTX_inv @ XTy
        self.intercept = beta[0]
        self.coefficients = beta[1:]
        
        # 预测值
        self.fitted_values = X_with_intercept @ beta
        
        # 残差
        self.residuals = y - self.fitted_values
        
        # 计算统计量
        n = len(y)
        k = X.shape[1]
        df = n - k - 1  # 自由度
        
        # MSE
        ss_res = np.sum(self.residuals ** 2)
        self.mse = ss_res / df
        
        # 协方差矩阵
        self.cov_matrix = self.mse * XTX_inv
        
        # 标准误
        self.std_errors = np.sqrt(np.diag(self.cov_matrix))
        
        # t统计量
        self.t_stats = beta / self.std_errors
        
        # p值（双尾检验）
        self.p_values = 2 * (1 - stats.t.cdf(np.abs(self.t_stats), df))
        
        # R²
        ss_total = np.sum((y - np.mean(y)) ** 2)
        self.r_squared = 1 - (ss_res / ss_total)
        
        # 调整R²
        self.adj_r_squared = 1 - ((1 - self.r_squared) * (n - 1) / df)
        
        return self
    
    def predict(self, X):
        """预测新数据"""
        X_with_intercept = np.column_stack([np.ones(X.shape[0]), X])
        beta = np.concatenate([[self.intercept], self.coefficients])
        return X_with_intercept @ beta
    
    def summary(self, feature_names=None):
        """输出回归结果摘要"""
        if feature_names is None:
            feature_names = [f'X{i+1}' for i in range(len(self.coefficients))]
        
        print("=" * 70)
        print("多元线性回归分析结果")
        print("=" * 70)
        print(f"R²: {self.r_squared:.4f}")
        print(f"调整R²: {self.adj_r_squared:.4f}")
        print(f"MSE: {self.mse:.4f}")
        print("-" * 70)
        print(f"{'变量':<15} {'系数':<12} {'标准误':<12} {'t统计量':<12} {'p值':<12}")
        print("-" * 70)
        
        # 截距项
        print(f"{'Intercept':<15} {self.intercept:<12.4f} {self.std_errors[0]:<12.4f} "
              f"{self.t_stats[0]:<12.4f} {self.p_values[0]:<12.6f}")
        
        # 自变量
        for i, name in enumerate(feature_names):
            print(f"{name:<15} {self.coefficients[i]:<12.4f} {self.std_errors[i+1]:<12.4f} "
                  f"{self.t_stats[i+1]:<12.4f} {self.p_values[i+1]:<12.6f}")
        
        print("=" * 70)

def calculate_vif(X, feature_names=None):
    """
    计算方差膨胀因子(VIF)
    X: 自变量矩阵
    """
    n_features = X.shape[1]
    vif_values = []
    
    if feature_names is None:
        feature_names = [f'X{i+1}' for i in range(n_features)]
    
    for i in range(n_features):
        # 构建辅助回归：X_i ~ 其他变量
        X_without_i = np.delete(X, i, axis=1)
        y_i = X[:, i]
        
        # OLS回归
        X_with_intercept = np.column_stack([np.ones(X_without_i.shape[0]), X_without_i])
        beta = np.linalg.inv(X_with_intercept.T @ X_with_intercept) @ X_with_intercept.T @ y_i
        
        # 计算R²
        y_pred = X_with_intercept @ beta
        ss_res = np.sum((y_i - y_pred) ** 2)
        ss_total = np.sum((y_i - np.mean(y_i)) ** 2)
        r_squared = 1 - (ss_res / ss_total)
        
        # VIF = 1 / (1 - R²)
        vif = 1 / (1 - r_squared)
        vif_values.append(vif)
    
    return vif_values

def residual_analysis(residuals, fitted_values, significance_level=0.05):
    """
    残差分析
    """
    print("\n" + "=" * 70)
    print("残差分析")
    print("=" * 70)
    
    # 1. 正态性检验（Shapiro-Wilk检验）
    shapiro_stat, shapiro_p = stats.shapiro(residuals)
    print(f"\n1. 正态性检验 (Shapiro-Wilk)")
    print(f"   统计量: {shapiro_stat:.4f}")
    print(f"   p值: {shapiro_p:.6f}")
    if shapiro_p > significance_level:
        print("   结论: 残差服从正态分布 (不能拒绝原假设)")
    else:
        print("   结论: 残差不服从正态分布 (拒绝原假设)")
    
    # 2. 异方差性检验（Breusch-Pagan检验）
    # 使用辅助回归: e² ~ ŷ
    n = len(residuals)
    residuals_squared = residuals ** 2
    
    # 构建辅助回归
    X_aux = np.column_stack([np.ones(n), fitted_values])
    beta_aux = np.linalg.inv(X_aux.T @ X_aux) @ X_aux.T @ residuals_squared
    fitted_aux = X_aux @ beta_aux
    
    # 计算LM统计量
    ssr_aux = np.sum((residuals_squared - fitted_aux) ** 2)
    sst_aux = np.sum((residuals_squared - np.mean(residuals_squared)) ** 2)
    r_squared_aux = 1 - (ssr_aux / sst_aux)
    lm_stat = n * r_squared_aux
    
    # p值（卡方分布，自由度为辅助回归的自变量数-1）
    bp_p_value = 1 - stats.chi2.cdf(lm_stat, 1)
    
    print(f"\n2. 异方差性检验 (Breusch-Pagan)")
    print(f"   LM统计量: {lm_stat:.4f}")
    print(f"   p值: {bp_p_value:.6f}")
    if bp_p_value > significance_level:
        print("   结论: 不存在异方差性 (不能拒绝原假设)")
    else:
        print("   结论: 存在异方差性 (拒绝原假设)")
    
    # 3. 残差统计描述
    print(f"\n3. 残差统计描述")
    print(f"   均值: {np.mean(residuals):.6f}")
    print(f"   标准差: {np.std(residuals, ddof=1):.4f}")
    print(f"   最小值: {np.min(residuals):.4f}")
    print(f"   最大值: {np.max(residuals):.4f}")
    print(f"   偏度: {stats.skew(residuals):.4f}")
    print(f"   峰度: {stats.kurtosis(residuals, fisher=True):.4f}")
    
    return {
        'shapiro_stat': shapiro_stat,
        'shapiro_p': shapiro_p,
        'bp_stat': lm_stat,
        'bp_p_value': bp_p_value
    }

def generate_simulation_data(n_samples=100, seed=42):
    """
    生成模拟数据
    """
    np.random.seed(seed)
    
    # 生成自变量
    Temperature = np.random.normal(20, 5, n_samples)  # 温度（°C）
    Precipitation = np.random.normal(100, 30, n_samples)  # 降水量（mm）
    GDP = np.random.normal(50000, 10000, n_samples)  # GDP（美元）
    Urbanization = np.random.uniform(30, 90, n_samples)  # 城市化率（%）
    
    # 构建自变量矩阵
    X = np.column_stack([Temperature, Precipitation, GDP, Urbanization])
    
    # 生成因变量（健康指标）
    # 假设真实关系: Health_Outcome = 70 - 0.5*Temperature - 0.3*Precipitation + 0.001*GDP + 0.2*Urbanization + 噪声
    true_intercept = 70
    true_coefficients = [-0.5, -0.3, 0.001, 0.2]
    
    y = true_intercept + X @ true_coefficients + np.random.normal(0, 5, n_samples)
    
    return X, y

def main():
    """
    主函数：执行完整的回归分析
    """
    print("=" * 70)
    print("多元回归分析脚本")
    print("模型: Health_Outcome ~ Temperature + Precipitation + GDP + Urbanization")
    print("=" * 70)
    
    # 1. 生成模拟数据
    print("\n[步骤1] 生成模拟数据...")
    X, y = generate_simulation_data(n_samples=200)
    feature_names = ['Temperature', 'Precipitation', 'GDP', 'Urbanization']
    print(f"    样本量: {len(y)}")
    print(f"    自变量数: {X.shape[1]}")
    
    # 2. 构建OLS回归模型
    print("\n[步骤2] 构建OLS回归模型...")
    model = MultipleLinearRegression()
    model.fit(X, y)
    model.summary(feature_names)
    
    # 3. 方差膨胀因子(VIF)检查
    print("\n[步骤3] 方差膨胀因子(VIF)检查多重共线性...")
    vif_values = calculate_vif(X, feature_names)
    print(f"\n{'变量':<15} {'VIF':<12} {'判断':<15}")
    print("-" * 42)
    for name, vif in zip(feature_names, vif_values):
        if vif > 10:
            judgment = "严重共线性"
        elif vif > 5:
            judgment = "中度共线性"
        else:
            judgment = "无严重共线性"
        print(f"{name:<15} {vif:<12.4f} {judgment:<15}")
    
    # 4. 残差分析
    print("\n[步骤4] 残差分析...")
    residual_results = residual_analysis(model.residuals, model.fitted_values)
    
    # 5. 输出总结
    print("\n" + "=" * 70)
    print("分析总结")
    print("=" * 70)
    print(f"1. 模型解释力: R² = {model.r_squared:.4f}")
    print(f"2. 调整R²: {model.adj_r_squared:.4f}")
    print(f"3. 回归方程:")
    equation = f"Health_Outcome = {model.intercept:.4f}"
    for i, (name, coef) in enumerate(zip(feature_names, model.coefficients)):
        sign = "+" if coef >= 0 else "-"
        equation += f" {sign} {abs(coef):.4f}×{name}"
    print(f"   {equation}")
    
    # 检查显著变量
    print(f"\n4. 显著变量 (α=0.05):")
    for i, (name, p_val) in enumerate(zip(feature_names, model.p_values[1:])):
        if p_val < 0.05:
            print(f"   ✓ {name} (p={p_val:.6f})")
        else:
            print(f"   ✗ {name} (p={p_val:.6f}) - 不